
import sys
import gc
import asyncio
import time
import upydash as _ 

from asyncio import Event
from primitives.delay_ms import Delay_ms
from primitives import Queue

from . import defs as mqtt_defs
from . import encdec as mqtt_encdec

from lib.debug import DebugMixin
from lib import byteify_pkt
from lib import cancel_gather_wait_for_ms


class MQTTCore(DebugMixin):
    def __init__(self, socket,
                       client_id, #bytes
                       username   = None,
                       password   = None,
                       will_topic = None,
                       will_msg   = None,
                       debug      = None,
                       ):
        self._name  = 'MQTT'

        self.client_id = client_id
        self.username = username
        self.password = password
        self.will_topic = will_topic
        self.will_msg = will_msg

        self.socket = socket

        self.rx_q  = self.socket.rx_q
        self.tx_q  = self.socket.tx_q

        #APPLICATION LAYER INTERFACE
        #pass messages up to application layer
        self.mqtt_app_rx_q  = Queue()
        #application to send messages, use publish/ping/subscribe/etc... directly

        self.tasks = []

        # list of all transmissions that we are expecting an ack for 
        self.qosacks_table   = []

        self.packet_id_incr = 0

        # track pingreq -> pingresp network delay
        self.ping_ticks_start = 0
        self.ping_delay_ms    = 0

        # pinger is use to induce a response from mqtt broker.  By sending a 
        # pingreq, we will receive a pingresp
        # pingresp will trigger the watchdog and prevent it from tripping
        self.pinger_ms = 2500
        self.pinger = Delay_ms(func     = self.ping,
                               duration = self.pinger_ms)

        # watchdog interval
        # we need to hear something from the mqtt broker at this interval or we assume
        # we are disconnected.
        # self.watchdog_ms = mqtt_defs.KEEP_ALIVE_S * 1000
        self.watchdog_ms = self.pinger_ms * 4
        self.watchdog_event = Event()
        self.watchdog       = Delay_ms(func     = lambda: self.watchdog_event.set(),
                                       duration = self.watchdog_ms)

        #event for when we receive connack.  context blocks until set
        self.got_connack = Event()

        # # timeout for initial connection ack
        # self.connack_timeout = Event()
        # self.connack_watch   = Delay_ms(func     = lambda: self.connack_timeout.set(),
                                        # duration = 5000)

    def set_client_id(self, client_id):
        self.client_id = client_id

    async def start(self):
        await self.adebug('start')
        await self.stop_tasks()

        #clear connack event
        self.got_connack.clear()

        ## clear qosacks except publishes
        self.qosacks_table[:] = _.filter(self.qosacks_table, lambda qosack: qosack.type == mqtt_defs.PUBLISH)
        
        self.tasks.append(asyncio.create_task(self.rx_coro()))
        self.tasks.append(asyncio.create_task(self.qosacks_coro()))

        self.packet_id_incr = time.ticks_cpu()%65536

        await self.connect()

    async def connect(self):
        while True:
            await self.adebug('connecting...')
            await self._connect(username   = self.username,
                                password   = self.password,
                                will_topic = self.will_topic,
                                will_msg   = self.will_msg)
            try:
                await asyncio.wait_for_ms(self.got_connack.wait(), 5000)
            except asyncio.TimeoutError as err:
                await self.adebug('connect failed')
                continue
            break
        await self.adebug('connected')

    async def stop_tasks(self):
        try:
            await cancel_gather_wait_for_ms(tasks      = self.tasks,
                                            timeout_ms = 5000)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
        finally:
            self.tasks.clear()

    async def stop(self, verbose=False):
        try:
            await self.adebug('STOP')
            await self.stop_tasks()

            if self.socket.socket_up.is_set():
                #if we still have a socket and are gracefully disconnecting
                #send the disconnect command
                await self.disconnect()
                await asyncio.sleep_ms(10) #give time for disconnect to tx

            self.watchdog.deinit()
            self.pinger.deinit()
            # self.connack_watch.deinit()

        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)

    async def __aenter__(self):
        try:
            await self.start()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
            await self.stop(verbose=True)
            raise
        return self

    async def __aexit__(self, *args):
        await self.stop()

    # Receive Coro
    async def rx_coro(self):
        try:
            #local access
            rx_q = self.rx_q
            rx_q_wait = rx_q.wait
            rx_q_empty = rx_q.empty
            rx_q_peek_len = rx_q.peek_len
            rx_q_get = rx_q.get_nowait
            process_pkt = self.process_pkt
            split_bytes_to_pkts = mqtt_encdec.split_bytes_to_pkts
            got_connack = self.got_connack.is_set
            pinger_trigger = self.pinger.trigger
            watchdog_trigger = self.watchdog.trigger

            #pre-allocate buffer
            max_len = 1024*5
            data = bytearray(max_len)
            mv = memoryview(data)

            idx = 0 #reset index outside of inner loop.  Inner loop idx tracks the residues
            while True: # mqtt protocol level timeout
                if got_connack(): #self.got_connack.is_set():
                    pinger_trigger()
                    watchdog_trigger()
                # idx = 0 # don't reset idx, we are keeping the residues
                itr = 0 # track the iteration
                await rx_q_wait()
                while True:
                    if rx_q_empty():
                        break
                    next_len = rx_q_peek_len()
                    if not next_len:
                        continue
                    if itr == 0 and next_len > max_len: #the data is bigger than the buffer -> grow the buffer
                        max_len = next_len
                        data = bytearray(max_len)
                        mv = memoryview(data)
                    if idx+next_len >= max_len:
                        break

                    ##################################################
                    # GET SOCKET RX DATA
                    # r = rx_q_get()
                    # await self.adebug('rx_coro', idx, next_len, idx+next_len, r, len(r))
                    # mv[idx:idx+next_len] = r
                    mv[idx:idx+next_len] = rx_q_get()
                    ##################################################

                    idx += next_len
                    itr += 1
                # await self.adebug('rx', idx)
                (pkt_splits, buff_from,) = split_bytes_to_pkts(mv[:idx])
                for pkt_split in pkt_splits:
                    await process_pkt(pkt = mv[pkt_split[0]:pkt_split[1]])
                # print(idx, buff_from, idx-buff_from)
                mv[0:idx-buff_from] = mv[buff_from:idx] #copy residue to front of buffer
                idx = idx-buff_from # update idx to account for residue

        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)

    async def process_pkt(self, pkt):
        try:
            # self.debug('process_pkt', len(pkt), bytes(pkt))
            try:
                mqtt_struct = mqtt_encdec.decode(pkt)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                sys.print_exception(err)
                self.debug('err decode', pkt)
                return
            if mqtt_struct.type == mqtt_defs.PUBLISH:
                # self.debug('rx', 'PUBLISH', mqtt_struct)
                # self.debug('rx', 'PUBLISH')

                ##################################################
                # Passing RX DATA up to MQTT ROOM/LOBBY
                await self.mqtt_app_rx_q.put(mqtt_struct.obj)
                ##################################################

                if mqtt_struct.obj.qos == 1: #PUBACK for qos==1
                    # await self.adebug('publish qos==1', 'respond with PUBACK')
                    await self.puback(packet_id = mqtt_struct.obj.packet_id)
            elif mqtt_struct.type == mqtt_defs.CONNACK:
                self.debug('rx','CONNACK', hex(mqtt_struct.obj.return_code),
                            mqtt_defs.connack_to_string(mqtt_struct.obj.return_code))
                if mqtt_struct.obj.return_code == mqtt_defs.CONNACK_RETURN_CODE_SUCCESS:
                    self.got_connack.set()
            elif mqtt_struct.type == mqtt_defs.PUBACK:
                # self.debug('rx', 'PUBACK', mqtt_struct, self.qosacks_table, mqtt_struct.obj.packet_id)
                qosack = _.find(self.qosacks_table, lambda qosack: qosack.packet_id == mqtt_struct.obj.packet_id)
                self.qosacks_table[:] = _.filter(self.qosacks_table, lambda qosack: qosack.packet_id != mqtt_struct.obj.packet_id)
                qosack.event.set()
            elif mqtt_struct.type == mqtt_defs.SUBACK:
                self.debug('rx', 'SUBACK', mqtt_struct)
                qosack = _.find(self.qosacks_table, lambda qosack: qosack.packet_id == mqtt_struct.obj.packet_id)
                self.qosacks_table[:] = _.filter(self.qosacks_table, lambda qosack: qosack.packet_id != mqtt_struct.obj.packet_id)
                qosack.event.set()
            elif mqtt_struct.type == mqtt_defs.UNSUBACK:
                self.debug('rx', 'UNSUBACK', mqtt_struct)
                qosack = _.find(self.qosacks_table, lambda qosack: qosack.packet_id == mqtt_struct.obj.packet_id)
                self.qosacks_table[:] = _.filter(self.qosacks_table, lambda qosack: qosack.packet_id != mqtt_struct.obj.packet_id)
                qosack.event.set()
            elif mqtt_struct.type == mqtt_defs.PINGRESP:
                self.ping_delay_ms = time.ticks_diff(time.ticks_ms(), self.ping_ticks_start)
                self.debug('rx', 'PINGRESP', self.ping_delay_ms,'ms')
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)

    # Check QosAcks table for any messages that have timedout and try them again
    async def qosacks_coro(self):
        #local access optimization
        publish = self.publish
        subscribe = self.subscribe
        unsubscribe = self.unsubscribe
        sleep_ms = asyncio.sleep_ms
        ticks_ms = time.ticks_ms
        ticks_diff = time.ticks_diff

        while True:
            _timeout_ms = mqtt_defs.QOS_ACKS_TIMEOUT_MS
            try:
                await sleep_ms(_timeout_ms)
                now = ticks_ms()
                # get expired
                expireds           = _.filter(self.qosacks_table, lambda qosack: ticks_diff(now, qosack.stamp) >= _timeout_ms)
                # get ids
                expired_ids = _.map(expireds, lambda qosack: qosack.packet_id)
                # remove all expired from table
                self.qosacks_table[:] = _.filter(self.qosacks_table, lambda qosack: qosack.packet_id not in expired_ids)

                for qosack in expireds:
                    if qosack.type == mqtt_defs.PUBLISH:
                        await publish(pkt       = qosack.pkt,
                                      packet_id = qosack.packet_id,
                                      try_count = qosack.try_count + 1,
                                      )
                    if qosack.type == mqtt_defs.SUBSCRIBE:
                        await subscribe(pkt       = qosack.pkt,
                                        packet_id = qosack.packet_id,
                                        try_count = qosack.try_count + 1,
                                        )
                    if qosack.type == mqtt_defs.UNSUBSCRIBE:
                        await unsubscribe(pkt       = qosack.pkt,
                                          packet_id = qosack.packet_id,
                                          try_count = qosack.try_count + 1,
                                          )

            except asyncio.CancelledError:
                raise
            except Exception as err:
                sys.print_exception(err)


    # @micropython.native
    def next_packet_id(self):
        while True:
            self.packet_id_incr = (self.packet_id_incr+1)%65536
            has_packet_id = _.find(self.qosacks_table, lambda qosack: qosack.packet_id == self.packet_id_incr)
            if has_packet_id == None:
                break
        return self.packet_id_incr

    async def publish(self, topic     = None,  #
                            payload   = None,  #
                            qos       = 0,     #
                            retain    = False,
                            packet_id = None,  #
                            try_count = 1,     #
                            pkt       = None,  # if we already have the pkt (re-posting) topic/payload/qos included
                            ):
        if payload != None:
            payload = byteify_pkt(payload)
        if payload == None or len(payload) == 0 and pkt == None:
            return
        if packet_id == None and qos != 0:
            packet_id = self.next_packet_id()
        if pkt == None:
            pkt = mqtt_encdec.encode_publish(topic     = topic,
                                                     payload   = payload,
                                                     packet_id = packet_id,
                                                     dupe      = try_count > 1,
                                                     retain    = retain,
                                                     qos       = qos,
                                                     )
        #pkt = b'0\x13\x00\x06ib0/up\x10\x00\x00\x00\x01\x00\x00\x03\xfe\x00\x11'
        if qos > 0:
            #only add to qos ack if we are qos>=1
            qosack = mqtt_defs.QOSAck(
                type      = mqtt_defs.PUBLISH,
                stamp     = time.ticks_ms(),
                try_count = try_count,
                pkt       = pkt,
                packet_id = packet_id,
                event     = Event(),
            )
            self.qosacks_table.append(qosack)
        await self.tx_q.put(pkt) #self.socket.tx_q
        if qos > 0:
            return qosack

    async def subscribe(self, topics,
                              qoss      = 1,
                              packet_id = None,  #
                              try_count = 1,     #
                              pkt       = None,  # if we already have the pkt (re-posting) topic/payload/qos included
                        ):
        if len(topics) == 0 and pkt == None:
            return
        if packet_id == None and qoss != 0:
            packet_id = self.next_packet_id()
        if pkt == None:
            topic_qoss = _.map(topics, lambda topic: (topic, qoss))
            pkt = mqtt_encdec.encode_subscribe(topic_qoss,
                                                       packet_id = packet_id,
                                                       )
        await self.adebug('tx', 'SUBSCRIBE', topics)
        if qoss > 0:
            qosack = mqtt_defs.QOSAck(
                type      = mqtt_defs.SUBSCRIBE,
                stamp     = time.ticks_ms(),
                try_count = try_count,
                pkt       = pkt,
                packet_id = packet_id,
                event     = Event(),
            )
            self.qosacks_table.append(qosack)
        await self.tx_q.put(pkt)#, is_priority=True) #self.socket.tx_q
        if qoss > 0:
            return qosack

    async def unsubscribe(self, topics,
                                packet_id = None,  #
                                try_count = 1,     #
                                pkt       = None,  # if we already have the pkt (re-posting) topic/payload/qos included
                         ):
        if len(topics) == 0 and pkt == None:
            return
        if packet_id == None:
            packet_id = self.next_packet_id()
        if pkt == None:
            pkt = mqtt_encdec.encode_unsubscribe(topics,
                                                         packet_id = packet_id,
                                                         )
        # await self.adebug('tx', 'UNSUBSCRIBE', topics)
        # always get unsuback
        qosack = mqtt_defs.QOSAck(
            type      = mqtt_defs.UNSUBSCRIBE,
            stamp     = time.ticks_ms(),
            try_count = try_count,
            pkt       = pkt,
            packet_id = packet_id,
            event     = Event(),
        )
        self.qosacks_table.append(qosack)
        await self.tx_q.put(pkt)#, is_priority=True) #self.socket.tx_q
        return qosack

    async def puback(self, packet_id):
        pkt = mqtt_encdec.encode_puback(packet_id = packet_id)
        # await self.adebug('tx', 'PUBACK', pkt)
        await self.tx_q.put(pkt)#, is_priority=True) #self.socket.tx_q

    async def ping(self):
        if not self.pinger:
            return
        self.pinger.trigger()
        if not self.got_connack.is_set():
            #don't send pingreq before connack
            return
        if self.tx_q.empty():
            #only add items if we are empty so we don't pile in
            pkt = mqtt_encdec.encode_pingreq()
            await self.adebug('pingreq')
            self.ping_ticks_start = time.ticks_ms()
            await self.tx_q.put(pkt)#, is_priority=True) #self.socket.tx_q

    async def _connect(self, username   = None,
                             password   = None,
                             will_topic = None,
                             will_msg   = None,
                             ):
        # await self.adebug('CONNECT', 'client_id', type(self.client_id), self.client_id)
        pkt = mqtt_encdec.encode_connect(client_id     = self.client_id,
                                         keep_alive    = mqtt_defs.KEEP_ALIVE_S,
                                         clean_session = True,
                                         username      = username,
                                         password      = password,
                                         will_topic    = will_topic,
                                         will_msg      = will_msg,
                                         )
        await self.adebug('CONNECT')
        self.pinger.trigger()
        await self.tx_q.put(pkt)#, is_priority=True) #self.socket.tx_q

    async def disconnect(self):
        pkt = mqtt_encdec.encode_disconnect()
        # await self.adebug('tx', 'DISCONNET', pkt)
        await self.tx_q.put(pkt)#, is_priority=True) #self.socket.tx_q

    async def debug_coro(self):
        try:
            while True:
                await asyncio.sleep(10)
                # await self.adebug('tasks')
                # for t in self.tasks:
                    # await self.adebug(t.coro,t.done())
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
