

try:
    #micropython
    from micropython import const
except:
    #python3
    from app.lib.micropython import const

import collections

QOS_ACKS_TIMEOUT_MS = const(5000)
KEEP_ALIVE_S        = const(30)

CONNECT_HEADER = b'\x00\x04MQTT'
PROTOCOL_LEVEL = const(0x04)

# Fixed header message types
CONNECT     = const(0x10)
CONNACK     = const(0x20) #always returned on connect attempt
PUBLISH     = const(0x30)
PUBACK      = const(0x40) #publish response when qos=1
SUBSCRIBE   = const(0x80)
SUBACK      = const(0x90) #always returned on sub
UNSUBSCRIBE = const(0xa0)
UNSUBACK    = const(0xb0)
PINGREQ     = const(0xc0)
PINGRESP    = const(0xd0)
DISCONNECT  = const(0xe0)

QOS_0 = const(0) # send only
QOS_1 = const(1) # receive puback
QOS_2 = const(2)

class MQTTTaskErr(Exception):
    pass
class MQTTLobbyTaskErr(Exception):
    pass
class MQTTRoomTaskErr(Exception):
    pass
class MQTTWatchdogTimeout(Exception):
    pass
class MQTTRoomWatchdogTimeout(Exception):
    pass
class MQTTLobbyWatchdogTimeout(Exception):
    pass
class MQTTLobbyStartTimeout(Exception):
    pass
class MQTTLobbyTimeout(Exception):
    pass
class MQTTRoomTimeout(Exception):
    pass
class MQTTConnAckTimeout(Exception):
    pass


FixedHeader_struct = collections.namedtuple('FixedHeader_struct',
    [
        'type',
        'remaining_length',
    ]
)

CONNACK_RETURN_CODE_SUCCESS         = const(0x00)
CONNACK_RETURN_CODE_ERR_PROTOCOL    = const(0x01)
CONNACK_RETURN_CODE_ERR_ID_REJECTED = const(0x02)
CONNACK_RETURN_CODE_ERR_SERVER_DOWN = const(0x03)
CONNACK_RETURN_CODE_ERR_BAD_AUTH    = const(0x04)
CONNACK_RETURN_CODE_ERR_NOT_AUTH    = const(0x05)
def connack_to_string(code):
    if code == CONNACK_RETURN_CODE_SUCCESS:
        return 'success'
    elif code == CONNACK_RETURN_CODE_ERR_PROTOCOL:
        return 'proto err'
    elif code == CONNACK_RETURN_CODE_ERR_ID_REJECTED:
        return 'clientid rej'
    elif code == CONNACK_RETURN_CODE_ERR_SERVER_DOWN:
        return 'server down'
    elif code == CONNACK_RETURN_CODE_ERR_BAD_AUTH:
        return 'bad auth'
    elif code == CONNACK_RETURN_CODE_ERR_NOT_AUTH:
        return 'not authorized'


ConnAck_struct = collections.namedtuple('ConnAck_struct',
    [
        'session_present',
        'return_code',
    ]
)

Publish_struct = collections.namedtuple('Pub_struct',
    [
        'packet_id',
        'qos',
        'topic',
        'payload',
    ]
)

PubAck_struct = collections.namedtuple('PubAck_struct',
    [
        'packet_id',
    ]
)

SubAck_struct = collections.namedtuple('SubAck_struct',
    [
        'packet_id',
        'sub_return_codes',
        'all_passed',
    ]
)

UnsubAck_struct = collections.namedtuple('UnsubAck_struct',
    [
        'packet_id',
    ]
)

Mqtt_struct = collections.namedtuple('Mqtt_struct',
    [
        'type',
        'obj',
    ]
)

#keep track of sent items so we can retry if we don't get an ack
QOSAck = collections.namedtuple('QOSAck',
    [
        'type',
        'stamp',
        'try_count',
        'pkt',
        'packet_id',
        'event',
    ]
)

