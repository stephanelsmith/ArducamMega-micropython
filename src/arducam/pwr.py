

from machine import Pin
from micropython import const

# UM FEATHER2 LDO2 
_LDO2 = const(21)

class ArduCamPwr():
    def __init__(self):
		self.ldo2 = Pin(_LDO2, Pin.OUT)
		self.ldo2.value(0)

    async def start(self):
		self.ldo2.value(1)

    async def stop(self, verbose=False):
        #high-z
		Pin(_LDO2, mode  = Pin.IN,
				   pull  = None,)

    async def __aenter__(self):
        try:
            await self.start()
        except:
            await self.stop()
            raise
        return self

    async def __aexit__(self, *args):
        await self.stop()

