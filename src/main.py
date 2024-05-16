
import asyncio
import sys
import gc
from machine import Pin, SPI

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

async def cam_coro():
    try:
        spi  = SPI(1, baudrate = 8000000, sck = Pin(36), mosi = Pin(35), miso = Pin(37))
        cs = Pin(7, Pin.OUT)
        cs.value(1)

        async with ArduCamPwr():
            async with ArduCam(spi = spi,
                               cs  = cs,
                               ) as arducam:
                await arducam.configure(resolution = RESOLUTION_96X96,
                                        )
                for x in range(10):
                    await arducam.capture()

    except asyncio.CancelledError:
        raise
    except Exception as err:
        sys.print_exception(err)
    finally:
        spi.deinit()

async def start():
    try:
        gc_task = asyncio.create_task(gc_coro())
        async with Wifi(addr = 0,
                        ) as wifi:
            async with WifiSocket(ifce   = wifi,
                                  host   = 'broker.hivemq.com',
                                  port   = 8883,
                                  en_ssl = True,
                                  ) as sock:
                # async with MQTTCore(socket    = sock,
                                    # client_id = wifi.client_id,
                                    # ) as mqtt:
                await asyncio.sleep(10)
        # await cam_coro()
    finally:
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

