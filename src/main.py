
import asyncio
import sys
import gc
from machine import Pin, SPI
import binascii
from asyncio import Event

from arducam.pwr import ArduCamPwr
from arducam.arducam import ArduCam
from arducam.arducam import RESOLUTION_640X480
from arducam.arducam import RESOLUTION_96X96

from wifi import Wifi
from wifi import WifiSocket

from mqtt.core import MQTTCore

async def gc_coro():
    try:
        while True:
            gc.collect()
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise
    except Exception as err:
        sys.print_exception(err)

async def start_cam(publish):
    try:
        spi  = SPI(1, baudrate = 8000000, sck = Pin(36), mosi = Pin(35), miso = Pin(37))
        cs = Pin(7, Pin.OUT)
        cs.value(1)

        async with ArduCamPwr():
            async with ArduCam(spi = spi,
                               cs  = cs,
                               ) as arducam:
                await arducam.configure(resolution = RESOLUTION_640X480,
                                        )
                while True:
                    print('capture')
                    jpg_mv = await arducam.capture()
                    # b64 = binascii.b2a_base64(jpg_mv)
                    print('jpg {}kB'.format(len(jpg_mv)//1000))
                    qosack = await publish(topic   = b'sscam/pix',
                                           payload = jpg_mv,
                                           qos     = 1,
                                           )
                    print('waiting for puback...')
                    await qosack.event.wait()


    except asyncio.CancelledError:
        raise
    except Exception as err:
        sys.print_exception(err)
    finally:
        spi.deinit()

async def mqtt_rx_coro(rx_q):
    try:
        while True:
            r = await rx_q.get()
            if r:
                print('RX',r)
    except asyncio.CancelledError:
        raise
    except Exception as err:
        sys.print_exception(err)

async def start():
    try:
        gc_task = asyncio.create_task(gc_coro())
        cam_task = None
        rx_task = None
        async with Wifi(addr = 0,
                        ) as wifi:
            use_ssl = False
            async with WifiSocket(ifce   = wifi,
                                  host   = 'broker.hivemq.com',
                                  en_ssl = use_ssl,
                                  port   = 8883 if use_ssl else 1883,
                                  ) as sock:
                async with MQTTCore(socket    = sock,
                                    client_id = wifi.client_id,
                                    ) as mqtt:
                    rx_task = asyncio.create_task(mqtt_rx_coro(rx_q = mqtt.mqtt_app_rx_q))
                    await mqtt.subscribe(topics = [b'sscam/cmd/#'])
                    cam_task = asyncio.create_task(start_cam(publish = mqtt.publish))
                    await Event().wait() # pause
    finally:
        if rx_task:
            rx_task.cancel()
        if cam_task:
            cam_task.cancel()
        gc_task.cancel()

def main():
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        pass
    except Exception as err:
        sys.print_exception(err)
    finally:
        asyncio.new_event_loop()  # Clear retained state

