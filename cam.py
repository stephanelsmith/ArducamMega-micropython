
import asyncio
import sys
import gc
from machine import Pin, SPI

from arducam.pwr import ArduCamPwr
from arducam.arducam import ArduCam

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
                await arducam.configure()
                for x in range(10):
                    await arducam.capture()

    except asyncio.CancelledError:
        raise
    except Exception as err:
        sys.print_exception(err)
    finally:
        spi.deinit()

async def main():
    try:
        gc_task = asyncio.create_task(gc_coro())
        await cam_coro()
    finally:
        gc_task.cancel()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
except Exception as err:
    sys.print_exception(err)
finally:
    asyncio.new_event_loop()  # Clear retained state

