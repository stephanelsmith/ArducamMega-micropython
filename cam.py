
import asyncio
import sys
from machine import Pin, SPI

from arducam.pwr import ArduCamPwr
from arducam.arducam import ArduCam

async def main():
    try:
        spi  = SPI(1, baudrate = 8000000, sck = Pin(36), mosi = Pin(35), miso = Pin(37))
        cs = Pin(7, Pin.OUT)
        cs.value(1)

        async with ArduCamPwr():
            async with ArduCam(spi = spi,
                               cs  = cs,
                               ) as arducam:
                await asyncio.sleep(1)

                r = await arducam.whoami()
                print(r)

                r = await arducam.capture()
                print(r)

    finally:
        spi.deinit()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
except Exception as err:
    sys.print_exception(err)
finally:
    asyncio.new_event_loop()  # Clear retained state

