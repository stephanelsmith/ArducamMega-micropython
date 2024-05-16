

import mqtt
from lib import coalesce_to_str_hexlify

print('\nconnect')
r = mqtt.encdec.encode_connect(client_id     = 'helloworld',
                        clean_session = False,
                        keep_alive    = 0,
                        username      = None,
                        password      = None,
                        )
print(r)
print(coalesce_to_str_hexlify(r))

print('\nconnack')
pkt = bytes([0x20, 0x02, 0x00, 0x00])
pktd = mqtt.encdec.decode(pkt)
print(pktd)


r = mqtt.encdec.encode_publish(dupe    = False,
                        qos     = 0,
                        retain  = False,
                        topic   = 'hello/world',
                        payload = bytes('hello larry', 'utf8'),
                        )
print(r)
print(coalesce_to_str_hexlify(r))

print('\npuback')
pkt = bytes([0x40, 0x02, 0x12, 0x34])
pktd = mqtt.encdec.decode(pkt)
print(pktd)


print('\nsubscribe')
r = mqtt.encdec.encode_subscribe(topic_qoss = [
                            ('hello/world',0),
                            ('foo/bar',1),
                          ],
                          packet_id = 12,
                        )
print(r)
print(coalesce_to_str_hexlify(r))

print('\nsubscribe time')
r = mqtt.encdec.encode_subscribe(topic_qoss = [
                            ('time/time',0),
                          ],
                          packet_id = 12,
                        )
print(r)
print(coalesce_to_str_hexlify(r))


print('\nsuback')
pkt = bytes([0x90, 5, 0x12, 0x34, 0, 2, 1])
pktd = mqtt.encdec.decode(pkt)
print(pktd)
pkt = bytes([0x90, 4, 0x12, 0x34, 0, 0x80])
pktd = mqtt.encdec.decode(pkt)
print(pktd)


print('\nunsubscribe')
r = mqtt.encdec.encode_unsubscribe(topics = [
                            'hello/world',
                            'foo/bar',
                          ],
                          packet_id = 12,
                        )
print(r)
print(coalesce_to_str_hexlify(r))


print('\nunsuback')
pkt = bytes([0xb0, 5, 0x12, 0x34])
pktd = mqtt.encdec.decode(pkt)
print(pktd)



print('\nping')
r = mqtt.encdec.encode_pingreq()
print(r)
print(coalesce_to_str_hexlify(r))

print('\nping resp')
pkt = bytes([0xd0, 0])
pktd = mqtt.encdec.decode(pkt)
print(pktd)



print('\ndisconnect')
r = mqtt.encdec.encode_disconnect()
print(r)
print(coalesce_to_str_hexlify(r))
