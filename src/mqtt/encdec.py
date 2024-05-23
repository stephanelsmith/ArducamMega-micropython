
import upydash as _ 
import random
from lib.b62 import _BASE62
from micropython import const
IS_UPY = 1

import struct
import binascii
from . import defs as mqtt_defs


#APPLICATION LEVEL
# CONNECT -> CONNACK (client_id required)
# PUBLISH -> no response when qos = 0
# PUBLISH -> PUBACK when qos = 1 (packet_id required)
# PUBLISH -> *qos=2 not implemented*
# SUBSCRIBE -> SUBACK (packet_id will match the SUBSCRIBE packet_id)
# UNSUBSCRIBE -> UNSUBACK (packet_id will match the UNSUBSCRIBE packet_id) 
# PINGREQ -> PINGRESP
# DISCONNECT -> *no response*


# https://docs.solace.com/API/MQTT-311-Prtl-Conformance-Spec/MQTT%20Control%20Packets.htm


#sockets outputting a stream of bytes, split bytes into pkts + remainder
#from mqtt.encdec import *
#a=bytes([0x90,0x3,0xcb,0x58,0x1])
#a=bytes([0x31,0x17,0x00,0x0a,0x69,0x62,0x30,0x2f,0x64,0x65,0x76,0x2f,0x64,0x6e,0x82,0xe0,0x74,0xe5,0xd4,0x00,0x00,0x00,0x00,0x01,0x9f])
#a=bytes([0x90,0x3,0xcb,0x58,0x1,0x90,0x3,0xcb,0x58,0x1,0x90,0x3,0xcb,0x58,0x1,0x90,0x3,0xcb,0x58,0x1,0x90,0x3,0xcb,0x58,0x1,0x90,0x3,0xcb,0x58,0x1,0x90,0x3,0xcb])
#split_bytes_to_pkts(a)
#encode_subscribe([('time/lcltime',0,)],)
# @micropython.native
def split_bytes_to_pkts(mv):
    #mv = memoryview(buff)
    i = 0
    headers = [mqtt_defs.CONNECT, mqtt_defs.CONNACK, mqtt_defs.PUBLISH, mqtt_defs.PUBACK, 
               mqtt_defs.SUBSCRIBE, mqtt_defs.SUBACK, 
               mqtt_defs.UNSUBSCRIBE, mqtt_defs.UNSUBACK, 
               mqtt_defs.PINGREQ, mqtt_defs.PINGRESP]
    do_break = False
    lenbuff = len(mv)
    pkt_splits = []
    while i < lenbuff and not do_break:  #two bytes is the minimum mqtt message length 
        if mv[i] in headers or\
           mv[i]&0xf0 == mqtt_defs.PUBLISH or\
           mv[i]&0xf0 == mqtt_defs.SUBSCRIBE   and mv[i]&0x02 or\
           mv[i]&0xf0 == mqtt_defs.UNSUBSCRIBE and mv[i]&0x02:
            # we need to allow lower nibble in publish (qos, dup, retain fields may be set)
            # we need to allow the lower reserved bit in sub and unsub

            # print('found header '+hex(mv[i]))
            (remaining_length, k) = decode_remaining_length(mv[i+1:i+1+4])
            # print('remaining_length', remaining_length, 'k', k)
            if remaining_length!=None and k!=None:
                # print('i+k+remaining_length', i+k+remaining_length, 'lenbuff', lenbuff)
                if i+k+remaining_length < lenbuff:
                    #we have all the bytes here
                    pkt_splits.append((i,i+k+remaining_length+1)) #split tuple
                    i += k+remaining_length+1
                else:
                    #we need more bytes
                    do_break = True
                    break
            else:
                if len(mv[i+1:i+1+4]) < 4:
                    #we need more bytes, remaining length is truncated
                    do_break = True
                    break
                else:
                    i += 1
        else:
            i += 1
    return (pkt_splits, i,)


# @micropython.native
def decode_remaining_length(mv):
    #from remaining length byte
    lenmv = len(mv)
    if lenmv >= 1 and mv[0]&0x80==0:
        return (mv[0]&0x7F, 1)
    elif lenmv >= 2 and mv[1]&0x80==0:
        return ((mv[0]&0x7F)+\
                (mv[1]&0x7F)*128,\
                2)
    elif lenmv >= 3 and  mv[2]&0x80==0:
        return ((mv[0]&0x7F)+\
                (mv[1]&0x7F)*128+\
                (mv[2]&0x7F)*128*128,\
                3)
    # elif lenmv >= 4 and mv[3]&0x80==0:
    elif lenmv == 4 and mv[3]&0x80==0:
        return ((mv[0]&0x7F)+\
                (mv[1]&0x7F)*128+\
                (mv[2]&0x7F)*128*128+\
                (mv[3]&0x7F)*128*128*128,\
                4)
    else:
        return (None, None)

    #decode remaining length algorithm adapted from doc
    #https://docs.solace.com/MQTT-311-Prtl-Conformance-Spec/MQTT%20Control%20Packet%20format.htm#_Ref355703004
    #k = 1
    #multiplier = 1
    #remaining_length = 0
    #while True:
        #if k==5: # we are on the 5th byte, invalid, remainging length only up to 4 bytes
            #i += 1
            #break
        #remaining_length += (mv[i+k]&0x7F) * multiplier
        #multiplier       *= 128
        #if i+1+k >= lenbuff or (mv[i+k]&0x80)==0:
            #break
        #k += 1
    #if k <= 4:
        #if i+k+remaining_length < lenbuff:
            ##we have all the bytes here
            #pkts.append(bytes(mv[i:i+k+remaining_length]))
            #i += k+remaining_length
        #else:
            #do_break = True
            #break

# @micropython.native
def encode_remaining_length(num_bytes):
    buff = bytearray(4)
    for idx in range(4):
        buff[idx] = num_bytes%128
        num_bytes //= 128
        if num_bytes == 0:
            break
        buff[idx] |= 0x80 #set continuation bit
    return buff[:idx+1]

# @micropython.native
def gen_packet_id():
    if IS_UPY:
        # return utime.ticks_cpu()%65536
        return random.randint(0,0xffff)
    else:
        return random.randint(0,0xffff)

#
#  CONNECT example, client_id = 'helloworld'
#  FIXED
#       ********* VARIABLE ***********
#                                      =====> PAYLOAD
#        1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 
#  10 16 00 04 4d 51 54 54 04 00 00 00 00 0a 68 65 6c 6c 6f 77 6f 72 6c 64
#         0  4  M  Q  T  T                    h  e  l  l  o  w  o  r  l  d
#  || CONNECT packet fixed header
#     || Remaining length 0x16 == 22
#        ||||||||||||||||| connect header
#                          || protocol level 4 = MQTT 3 
#                             || Connnect flags (username, password, will retian, will qos, qill flag, clean session, reserved)
#                                || || Keep alive 
#                                      || || payload 1 (client_id) length
#                                             |||||||||||||||||||||||||||| client_id
# @micropython.native
def encode_connect(client_id,        # unique Client identifier for the Client (string, only using B62 characters)
                   keep_alive    = 600,    # client must ping within this timeout
                   clean_session = True, # The Client and Server can store Session state to enable reliable messaging to continue across a sequence of Network Connections. This bit is used to control the lifetime of the Session state.
                   username      = None,
                   password      = None,
                   will_topic    = None,
                   will_msg      = None,
                   ):
    varlen = 2 + len(client_id)
    for payload in [will_topic, will_msg, username, password]:
        if payload:
            varlen = varlen + 2 + len(payload)

    lc = 12
    r = bytearray(lc + varlen)
    r[0] = mqtt_defs.CONNECT
    r[1] = len(r) - 2 #remaining length
    r[2:2+6] = mqtt_defs.CONNECT_HEADER
    r[8] = mqtt_defs.PROTOCOL_LEVEL

    #connection flag
    if username:
        r[9] |= 0x80 #username
        r[9] |= 0x40 #password
    if will_topic and will_msg:
        r[9] |= 0x04
    if clean_session:
        r[9] |= 0x02

    # r += struct.pack('>H', keep_alive) # keep alive
    r[10:10+2] = struct.pack('>H', keep_alive)

    #client_id
    #client_id can only use "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    #that is, it's b62 encoded version of arbitrary bytes
    b62 = _BASE62
    for c in client_id:
        if c not in b62:
            raise Exception('client_id encoding error '+str(client_id)+' not inclusive of '+b62)
    r[lc:lc+2] = struct.pack('>H', len(client_id))
    lc += 2
    r[lc:lc+len(client_id)] = bytes(client_id, 'utf8')
    lc += len(client_id)

    #payload items, item presence is dependent on connection flags
    for payload in [will_topic, will_msg, username, password]:
        if payload:
            if isinstance(payload, str):
                payload = bytes(payload, 'utf8')
            elif isinstance(payload, bytes):
                pass
            else:
                payload = bytes(payload)
            r[lc:lc+2] = struct.pack('>H', len(payload))
            lc += 2
            r[lc:lc+len(payload)] = payload
            lc += len(payload)

    return r


#  PUBLISH example, topic='hello/world', qos=0, message='hello larry'
#  FIXED
#       ********* VARIABLE ********************
#                                               =====> PAYLOAD
#        1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
#  30 18 00 0b 68 65 6c 6c 6f 2f 77 6f 72 6c 64 68 65 6c 6c 6f 20 6c 61 72 72 79
#         0 11  h  e  l  l  o  /  w  o  r  l  d  h  e  l  l  o     l  a  r  r  y
#  || PUBLUSH packet fixed header
#     || Remaining length 0x18 == 24
#        ||||| topic length
#               ||||||||||||||||||||||||||||||| topic name
#                                               |||||||||||||||||||||||||||||||| message
# @micropython.native
def encode_publish(topic,     #bytes/str/bytearray,
                   payload,   #bytes/str/bytearray/memoryview
                   dupe      = False,    # is a re-delivery attempt? 0 means first time
                   qos       = 0,        # qos
                   retain    = True,     # message retained for future subscribers
                   packet_id = None,     # only valid for qos 1 and 2, if None, generate one
                    ):
    #single memory allocation version (faster)
    #if qos!=0, then we have the packet_id between topic name and message
    packet_id_len = 2 if qos == mqtt_defs.QOS_1 or qos == mqtt_defs.QOS_2 else 0

    varlen = 2 + len(topic) + packet_id_len + len(payload)
    remaining_length_bytes = encode_remaining_length(varlen)
    r = bytearray(1 + len(remaining_length_bytes) + varlen)

    header = mqtt_defs.PUBLISH
    if dupe:
        header |= 0x08
    header |= (qos<<1)
    if retain:
        header |= 0x01
    r[0] = header
    offset = 1
    
    #remaining length
    r[offset:offset+len(remaining_length_bytes)] = remaining_length_bytes
    offset += len(remaining_length_bytes)
    
    #topic length
    r[offset:offset+2] = len(topic).to_bytes(2,'big')
    offset += 2

    #topic
    if isinstance(topic, str):
        r[offset:offset+len(topic)] = bytes(topic, 'utf8')
    else: #if isinstance(topic, (bytes, bytearray, memoryview))::
        r[offset:offset+len(topic)] = topic
    offset += len(topic)

    #packet_id if qos1
    if qos == mqtt_defs.QOS_1 or qos == mqtt_defs.QOS_2:
        if packet_id == None:
            packet_id = gen_packet_id()
        r[offset:offset+2] = (packet_id).to_bytes(2,'big')
        offset += 2

    #payload
    if isinstance(payload, str):
        r[offset:] = bytes(payload, 'utf8')
    else: #if isinstance(payload, (bytes, bytearray, memoryview)):
        r[offset:] = payload
    # else:
        # raise Exception('publish payload should be bytes/str')
    return r



#  SUBSCRIBE example, packet_id=12, topics=('hello/world', qos=0), ('foo/bar', qos=1)
#  FIXED
#       *VARI*
#              ==========> PAYLOAD
#        1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
#  82 1a 00 0c 00 0b 68 65 6c 6c 6f 2f 77 6f 72 6c 64 00 00 07 66 6f 6f 2f 62 61 72 01
#           12    11  h  e  l  l  o  /  w  o  r  l  d        7  f  o  o  /  b  a  r
#  || SUBSCRIBE packet fixed header
#     || Remaining length 0x1a == 26
#        ||||| packet_id (12)
#              ||||| topic 1 length
#                    ||||||||||||||||||||||||||||||||    topic 1 name
#                                                     || topic 1 qos
#                                                        ||||| topic 2 length
#                                                              ||||||||||||||||||||    topic 2 name
#                                                                                   || topic 2 qos
### TODO, FIXED ARRAY SIZE!!!
# @micropython.native
def encode_subscribe(topic_qoss,       # list of tuple (topic str, qos)
                     packet_id = None, # required, SUBACK will response with packet_id_
                     ):
    r = bytearray()
    header = mqtt_defs.SUBSCRIBE
    header |= 0x02 #per spec., reserved lower nibble set to 0x02 for subscribe

    #packet_id
    if packet_id == None:
        packet_id = gen_packet_id()
    #r += struct.pack('>H', packet_id)
    r += (packet_id).to_bytes(2,'big')

    for topic_qos in topic_qoss:
        topic = topic_qos[0]
        qos   = topic_qos[1]
        #r += struct.pack('>H', len(topic)) #length of this payload item
        r += len(topic).to_bytes(2,'big')
        if isinstance(topic, str):
            r += bytes(topic, 'utf8')
        else: #if isinstance(topic, (bytes, bytearray, memoryview))::
            r += topic
        #r += struct.pack('>B', qos) # qos
        r += (qos).to_bytes(1,'big')

    #      fixed header    + remaining length                + payload
    return bytes([header]) + encode_remaining_length(len(r)) + r


#  UNSUBSCRIBE 
#  FIXED
#       *VARI*
#              ==========> PAYLOAD
#        1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
#  a2 18 00 0c 00 0b 68 65 6c 6c 6f 2f 77 6f 72 6c 64 00 07 66 6f 6f 2f 62 61 72
#           12    11  h  e  l  l  o  /  w  o  r  l  d     7  f  o  o  /  b  a  r
#  || SUBSCRIBE packet fixed header
#     || Remaining length 0x18 == 24
#        ||||| packet_id (12)
#              ||||| topic 1 length
#                    ||||||||||||||||||||||||||||||||    topic 1 name
#                                                     ||||| topic 2 length
#                                                           ||||||||||||||||||||    topic 2 name
# @micropython.native
def encode_unsubscribe(topics,           # list of topics
                       packet_id = None, # required, SUBACK will response with packet_id_
                       ):
    r = bytearray()
    header = mqtt_defs.UNSUBSCRIBE
    header |= 0x02 #per spec., reserved lower nibble set to 0x02 for subscribe

    #packet_id
    if packet_id == None:
        packet_id = gen_packet_id()
    #r += struct.pack('>H', packet_id)
    r += (packet_id).to_bytes(2,'big')

    for topic in topics:
        #r += struct.pack('>H', len(topic)) #length of this payload item
        r += len(topic).to_bytes(2,'big')
        if isinstance(topic, str):
            r += bytes(topic, 'utf8')
        else: #if isinstance(topic, (bytes, bytearray, memoryview))::
            r += topic

    #      fixed header    + remaining length                + payload
    return bytes([header]) + encode_remaining_length(len(r)) + r

# Puback
# @micropython.native
def encode_puback(packet_id):
    return struct.pack('>BBH', mqtt_defs.PUBACK, 2, packet_id)

# Ping Request
# @micropython.native
def encode_pingreq():
    return bytes([mqtt_defs.PINGREQ, 0])

# Disconnect
# @micropython.native
def encode_disconnect():
    return bytes([mqtt_defs.DISCONNECT, 0])


# @micropython.native
def decode_connack(pktmv):
    (session_present, return_code,) = struct.unpack('>BB', pktmv[2:])
    return mqtt_defs.ConnAck_struct(
        session_present = session_present,
        return_code     = return_code,
    )



#   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25
#  30 18 00 0b 68 65 6c 6c 6f 2f 77 6f 72 6c 64 68 65 6c 6c 6f 20 6c 61 72 72 79
#         0 11  h  e  l  l  o  /  w  o  r  l  d  h  e  l  l  o     l  a  r  r  y
#  || PUBLUSH packet fixed header
#     || Remaining length 0x18 == 24
#        ||||| topic length
#               ||||||||||||||||||||||||||||||| topic name
#                                               |||||||||||||||||||||||||||||||| message
#from mqtt.encdec import *
#a=bytes([0x30,0x26,0x0,0x8,0x74,0x69,0x6d,0x65,0x2f,0x72,0x74,0x63,0x28,0x32,0x30,0x32,0x31,0x2c,0x30,0x35,0x2c,0x31,0x30,0x2c,0x31,0x37,0x2c,0x33,0x36,0x2c,0x32,0x31,0x2c,0x39,0x39,0x39,0x39,0x31,0x34,0x29])
#decode_publish(memoryview(a))
#decode_remaining_length(memoryview(a))
# @micropython.native
def decode_publish(mv):
    control = mv[0]
    (remaining_length, k) = decode_remaining_length(mv[1:5])
    # print('remaining_length', remaining_length, 'k', k)
    (topic_len,) = struct.unpack('>H', mv[1+k:1+k+2])
    # print('topic_len '+str(topic_len))
    topic_offset = 1+k+2
    topic   = mv[topic_offset:topic_offset+topic_len]
    # print('topic ' +str(bytes(topic)))

    #packet_id only present if qos==1
    qos     = (control & 0x06)>>1
    if qos == 0:
        packet_id = None
        payload_offset = topic_offset+topic_len
    else:
        (packet_id,) = struct.unpack('>H', mv[topic_offset+topic_len:topic_offset+topic_len+2])
        payload_offset = topic_offset+topic_len+2

    #print('payload_offset ' +str(payload_offset))
    payload = mv[payload_offset:remaining_length+1+k]
    #print('payload ' +str(bytes(payload)))
    return mqtt_defs.Publish_struct(
        packet_id = packet_id,
        qos       = qos,
        topic     = bytes(topic).decode(), #topic must be utf8
        payload   = bytes(payload),
    )

# @micropython.native
def decode_puback(pktmv):
    #QOS 1 only
    (packet_id,) = struct.unpack('>H', pktmv[2:])
    return mqtt_defs.PubAck_struct(
        packet_id     = packet_id,
    )

# @micropython.native
def decode_suback(pktmv):
    #always returned on sub
    (packet_id,) = struct.unpack('>H', pktmv[2:4])
    sub_return_codes = [x for x in pktmv[4:]]
    all_passed = _.all(sub_return_codes, lambda code: code != 0x80)
    return mqtt_defs.SubAck_struct(
        packet_id        = packet_id,
        sub_return_codes = sub_return_codes,
        all_passed       = all_passed,
    )

# @micropython.native
def decode_unsuback(pktmv):
    (packet_id,) = struct.unpack('>H', pktmv[2:])
    return mqtt_defs.UnsubAck_struct(
        packet_id     = packet_id,
    )

# @micropython.native
def decode_pingresp(pktmv):
    return None


# @micropython.native
def decode(pkt):
    mv = memoryview(pkt)

    # print(binascii.hexlify(mv[0:20],','))

    (mqtt_type, remaining_length,) = struct.unpack('>BB', mv[:2])
    mqtt_type &= 0xf0 #mask out lower nibble

    # print('mqtt_type', hex(mqtt_type))
   
    obj = None
    if mqtt_type == mqtt_defs.CONNACK:
        obj = decode_connack(mv)
    elif mqtt_type == mqtt_defs.PUBACK:
        obj = decode_puback(mv)
    elif mqtt_type == mqtt_defs.SUBACK:
        obj = decode_suback(mv)
    elif mqtt_type == mqtt_defs.UNSUBACK:
        obj = decode_unsuback(mv)
    elif mqtt_type == mqtt_defs.PINGRESP:
        obj = decode_pingresp(mv)
    elif mqtt_type == mqtt_defs.PUBLISH:
        obj = decode_publish(mv)
    else:
        raise Exception('no mqtt decoder for '+str(bytes(mqtt_type)))
    
    return mqtt_defs.Mqtt_struct(
        type = mqtt_type,
        obj  = obj,
    )

