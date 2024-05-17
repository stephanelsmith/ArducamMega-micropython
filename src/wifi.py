
import sys
from micropython import const
import machine

import asyncio
import socket
import tls
import network
import time
import errno
import uctypes
from asyncio import Event
from primitives import Queue
import binascii
import collections

import upydash as _ 
from lib import SocketClosed
from lib import cancel_gather_wait_for_ms
from lib.debug import DebugMixin


_BUSY_ERRORS = [errno.EINPROGRESS, errno.ETIMEDOUT, 118, 119]
_SOCKET_POLL_DELAY = const(10) #slow poll delay so we don't slam

# AP names are pre-fixes, essentially SSID.*
APs = [
    (b'GL-',b'goodlife'),
    (b'ThunderFace',b'sararocksmyworld'),
]

#socket.getaddrinfo is blocking.  Keep global list of results so we don't block
#more than once
AddrInfos =[]
AddrInfo = collections.namedtuple('AddrInfo',
    [
        'host',
        'port',
        'addrinfo',
    ]
)

_WIFI_TX_POWER     = const(8) #dBm

class WifiSocket(DebugMixin):
    def __init__(self, ifce     = None,
                       host     = None, 
                       port     = None,
                       en_ssl   = True,
                       tx_q     = None,
                       ):
        self._name  = 'WIFISOCK'

        self.wifi = ifce
        # self.rtr_ifce = ifce
        self.sock = None
        self.host = host
        self.port  = port
        self.en_ssl = en_ssl
        self.addr_info = None

        self.rx_q   = Queue()

        # use provided tx_q, or create our own
        if not tx_q:
            self.tx_q   = Queue()
        else:
            self.tx_q   = tx_q

        #track if a socket is open or closed, used for retry methods
        #don't set these directly, use set_socket_status(is_ready=
        self.socket_down = Event()
        self.socket_up   = Event()

        #used by caller to determine if socket is good
        # self.is_ready = self.socket_up

        self.tasks        = [] 

        #stats
        self.ticks_start = time.ticks_ms()
        self.rx_count = 0    #rx bytes/sec
        self.tx_count = 0    #tx bytes/sec

    async def start(self):
        await self.adebug('start')

        # pause until the socket is ready, timeout so we don't forever block in await with
        # await self.start_socket()
        try:
            await asyncio.wait_for_ms(self.start_socket(),60000)
        except asyncio.TimeoutError:
            raise SocketClosed
        except asyncio.CancelledError:
            raise

        self.tasks.append(asyncio.create_task(self.rx_coro()))
        self.tasks.append(asyncio.create_task(self.tx_coro()))
        self.tasks.append(asyncio.create_task(self.debug_coro()))

    async def stop_tasks(self):
        try:
            await cancel_gather_wait_for_ms(tasks      = self.tasks,
                                            timeout_ms = 3000)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
        finally:
            self.tasks.clear()

    async def stop(self, verbose=False):
        try:
            await self.adebug('stop')
            if self.sock:
                # self.debug('closing socket (stop)', id(self.sock))
                self.sock.close()
            await self.stop_tasks()
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
            await self.stop()
            raise
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start_socket(self):
        await self.adebug('start_socket')
        try:
            #wait until wifi is up and registered with a network
            await self.wifi._ap_connected.wait()

            #get socket info
            tries = 3
            while True:
                try:
                    addrinfo = self.get_socket_info(host = self.host,
                                                    port = self.port,)
                    break
                except asyncio.CancelledError:
                    raise
                except OSError as e:
                    if e.args[0] == -202:
                        tries -= 1
                        if tries == 0:
                            raise
                        await asyncio.sleep(1)

            # if self.sock:
                # self.debug('closing socket (loop)', id(self.sock))
                # self.sock.close()
            self.sock = socket.socket()
            self.sock.setblocking(False)

            try:
                self.sock.connect(addrinfo)
            except OSError as e:
                # esp32 https://github.com/micropython/micropython-esp32/issues/166
                if e.args[0] not in _BUSY_ERRORS:
                    raise
            except asyncio.CancelledError:
                raise
            except Exception as err:
                sys.print_exception(err)
                await asyncio.sleep_ms(_SOCKET_POLL_DELAY)
            await self.adebug('connected', self.host, self.port)

            if self.en_ssl:
                ctx = tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
                ctx.verify_mode = tls.CERT_OPTIONAL
                self.sock = ctx.wrap_socket(self.sock)
        
            self.set_socket_status(is_ready = True)

        except asyncio.CancelledError:
            raise
        except Exception as err:
            # await self.adebug('socket_watcher_coro', 'err')
            sys.print_exception(err)

    async def rx_coro(self):
        try:
            # print('testing socket', 'rx_coro', id(self.sock))
            # r = self.sock.write(bytes(10))

            #local access
            socket_up = self.socket_up
            socket_up_wait = self.socket_up.wait
            socket_up_is_set = self.socket_up.is_set
            rx_q = self.rx_q
            rx_q_put = rx_q.put
            sleep_ms = asyncio.sleep_ms

            #pre-allocate buffer
            max_len = 1024*5
            data = bytearray(max_len)
            mv = memoryview(data)

            await socket_up_wait()
            # we get new sockets, after each socker up
            sock_readinto = self.sock.readinto 
            while True:
                if not socket_up_is_set():
                    break
                await sleep_ms(_SOCKET_POLL_DELAY)
                n = sock_readinto(data)
                if n:
                    #we need to pass in a copy into the queue since we will overwrite the same buffer next iteration
                    await rx_q_put(bytes(mv[:n]))
                    self.rx_count += n
                    n = 0

            # await socket_up_wait()
            # sock_read = self.sock.read 
            # while True:
                # if not socket_up_is_set():
                    # break
                # await sleep_ms(_SOCKET_POLL_DELAY)
                # buff = None
                # try:
                    # # when reading, we always are reading in the bytes buffer
                    # # since we need to pass the copy to put
                    # # we don't need to read_into since we'd create a copy anyway
                    # buff = sock_read(max_len)
                    # if buff:
                        # await rx_q_put(buff)
                # except asyncio.CancelledError:
                    # raise

        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
            self.set_socket_status(is_ready = False)
            # self.update_gateway_ifce(is_ready = False) #immediately stop routing data to this gateway
            return
        finally:
            print('RX SOCK CLOSE', self.sock, id(self.sock))

    async def tx_coro(self):
        try:
            #local access
            tx_q = self.tx_q
            tx_q_wait = tx_q.wait
            tx_q_empty = tx_q.empty
            tx_q_peek_len = tx_q.peek_len
            tx_q_get = tx_q.get_nowait
            socket_up = self.socket_up
            socket_up_is_set = socket_up.is_set
            socket_down = self.socket_down
            socket_down_is_set = socket_down.is_set
            sleep_ms = asyncio.sleep_ms

            #pre-allocate buffer
            max_len = 1024*5
            data = bytearray(max_len)
            mv = memoryview(data)

            cnt = 0
            idx = 0

            await socket_up.wait()
            sock_write = self.sock.write
            while True:
                idx = 0
                cnt = 0
                if not socket_up_is_set() or socket_down_is_set():
                    raise Exception('Socket is closed')
                await tx_q_wait() #wait for item without getting item
                while True:
                    if tx_q_empty():
                        break
                    next_len = tx_q_peek_len()
                    if not next_len:
                        continue
                    if idx == 0 and next_len > max_len: #the data is bigger than the buffer -> grow the buffer
                        max_len = next_len
                        data = bytearray(max_len)
                        mv = memoryview(data)
                    if idx+next_len > max_len:
                        break
                    mv[idx:idx+next_len] = tx_q_get()
                    # print('tx_coro 1', next_len)
                    idx += next_len
                    cnt += 1
                n = 0
                while n < idx:
                    # write returns None if not successful instead of raising EAGAIN like send
                    r = sock_write(mv[n:idx])
                    if not r: #None or 0
                        # print('tx_coro 2', idx-n)
                        await sleep_ms(100)
                    else:
                        n += r
                        await sleep_ms(0) #release scheduling to asyncio

                #throughput
                self.tx_count += n

                    # alternative version with send.  send throws EAGAIN, requires a try block
                    # try:
                        # r = sock.send(mv[n:idx])
                        # if not r: #None or 0
                            # await sleep_ms(10)
                        # else:
                            # n += r
                            # await sleep_ms(0) #don't lock up
                    # except OSError as err:
                        # # sys.print_exception(err)
                        # if err.args[0] == errno.EAGAIN: #OSError: [Errno 11] EAGAIN
                            # #socket busy
                            # await sleep_ms(10)

        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
        finally:
            print('TX SOCK CLOSE', self.sock, id(self.sock))
            self.set_socket_status(is_ready = False)

            # TODO, this is an issue, this interferes with the NEXT connection attempt, sending data out of sequence
            # self.tx_q._p_queue = [] #clear the priority queue
            # if idx:
                # self.tx_q._queue.insert(0,bytes(mv[:idx])) #add unsent items back into queue


    def get_socket_info(self, host, port):
        # Note this blocks if DNS lookup occurs. Do it once to prevent
        # blocking during later internet outage:
        addrinfo = _.find(AddrInfos, lambda addrinfo: addrinfo.host == host and addrinfo.port == port)
        # addrinfo = None # always do DNS lookup
        if not addrinfo:
            addrinfo = AddrInfo(
                host      = host,
                port      = port,
                addrinfo = socket.getaddrinfo(host, port)[0][-1],
            )
            AddrInfos.append(addrinfo)
        return addrinfo.addrinfo


    def set_socket_status(self, is_ready):
        if is_ready:
            self.socket_down.clear()
            self.socket_up.set()
        else:
            self.socket_down.set()
            self.socket_up.clear()

    async def debug_coro(self):
        #local access optimization
        sleep = asyncio.sleep
        adebug = self.adebug

        try:
            while True:
                await sleep(10)
                #throughput report
                ticks = time.ticks_diff(time.ticks_ms(), self.ticks_start)
                await adebug( 'RX B/s',self.rx_count/(ticks/1000),
                              'TX B/s',self.tx_count/(ticks/1000),)
                await adebug('---------')
                self.ticks_start = time.ticks_ms()
                self.rx_count = 0
                self.tx_count = 0
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)



class Wifi(DebugMixin):
    def __init__(self, addr     = None,
                       ):
        self._name  = 'WIFI'

        self.addr     = addr

        self.sta = network.WLAN(network.STA_IF)
        self.mac  = self.sta.config('mac')

        #don't set these directly, use set_connected_ap(is_connectped=
        self._ap_connected = Event()
        self._ap_not_connected = Event()

        self.tasks = []

    @property
    def client_id(self):
        return binascii.hexlify(self.mac).decode()

    async def start(self):
        await self.adebug('start')
        await self.stop_tasks()

        self.set_connected_ap(is_connected = False)

        #initialize and start the wifi module
        self.tasks.append(asyncio.create_task(self.conn_coro())) #coro to setup the socket

        # self.set_wifi_state(is_up = True)

    async def stop_tasks(self):
        try:
            await cancel_gather_wait_for_ms(tasks      = self.tasks,
                                            timeout_ms = 3000)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)
        finally:
            self.tasks.clear()

    async def stop(self, verbose=False):
        try:
            await self.adebug('stop')
            await self.stop_tasks()
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
            await self.stop()
            raise
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def conn_coro(self):
        # await self.adebug('conn_coro', 'start')
        try:
            while True:
                try:
                    if len(APs) == 0:
                        raise Exception('no aps')
                    self.sta.active(True)
                    self.sta.config(txpower = _WIFI_TX_POWER)
                    # self.sta.config(pm=self.sta.PM_POWERSAVE)
                    await self.connect_knownap(verbose=True)
                    if not self.sta.isconnected():
                        await asyncio.sleep(1)
                        continue

                    #connected!
                    await self.adebug('ip', self.ip())

                    #allow wifisocket to continue
                    self.set_connected_ap(is_connected = True)

                    #wait
                    await self._ap_not_connected.wait()
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    sys.print_exception(err)
                finally:
                    self.set_connected_ap(is_connected = False)
                    if self.sta.isconnected():
                        self.sta.disconnect()
                    self.sta.active(False)
                
        except asyncio.CancelledError:
            raise

    async def connect_knownap(self, verbose=False):
        try:
            while True:

                # super annoying block wifi scan
                # would be cool if non-blocking scan introduced....
                # https://github.com/micropython/micropython/pull/7526
                await self.adebug('wifi scan...')
                scan_results = self.sta.scan()
                #scan result tuple (ssid, bssid, channel, RSSI, security, hidden)
                scan_results = _.sort_by(scan_results, lambda r: r[3])

                self.sta.disconnect() 
                for scan_ap in scan_results[::-1]:
                    await self.adebug('wifi scan',scan_ap)
                    for ap in APs:
                        my_ssid = ap[0]
                        scan_ssid = scan_ap[0]
                        mv = memoryview(scan_ssid)
                        if my_ssid == mv[:len(my_ssid)]:
                            if verbose:
                                await self.adebug('trying', scan_ssid, ap[1])
                            self.sta.connect(scan_ssid, ap[1])
                            start = time.ticks_ms()
                            while time.ticks_diff(time.ticks_ms(), start) < 10000 and not self.sta.isconnected():
                                await asyncio.sleep_ms(250)
                            if self.sta.isconnected():
                                await self.adebug('connected to', scan_ssid, ap[1])
                                return 
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            sys.print_exception(err)

    def set_connected_ap(self, is_connected):
        if is_connected:
            self._ap_connected.set()
            self._ap_not_connected.clear()
        else:
            self._ap_connected.clear()
            self._ap_not_connected.set()

    # #wifi.ip()
    def ip(self):
        try:
            return self.sta.ifconfig()[0]
        except asyncio.CancelledError:
            raise
        except:
            return '0.0.0.0'
        

