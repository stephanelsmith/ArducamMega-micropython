

import asyncio
from micropython import const

import time
from machine import Pin
import binascii
import os

_REG_WHOAMI = const(0x40)

_REG_BASIC_CFG = const(0x20)
_PIXEL_FORMAT_JPG = const(0x01)

_REG_RESOLUTION = const(0x21)
_RESOLUTION_640X480 = const(0X02)

_REG_MEMORY_CTRL = const(0x04)
_CLEAR_MEMORY    = const(0x01)
_START_PICTURES  = const(0x02)


ARDUCHIP_TRIG = 0x44
CAP_DONE_MASK = 0x04

FIFO_SIZE1 = 0x45
FIFO_SIZE2 = 0x46
FIFO_SIZE3 = 0x47


class ArduCam():
    def __init__(self, spi,
                       cs,
                       ):
		self.spi = spi
		self.cs  = cs

    async def start(self, timeout = 2000):
        t = time.ticks_ms()
        while True:
            r = await self.whoami(verbose = False)
            # print('{:02X}'.format(r))
            if r != 0 and r != 0xff:
                break
            delta = time.ticks_diff(time.ticks_ms(), t)
            if delta > timeout:
                raise Exception('timed out connecting to ArduCam : {:02X}'.format(r))
            await asyncio.sleep_ms(10)
        print('connected to arducam: {:02X}, {}ms'.format(r, delta))

    async def stop(self, verbose=False):
        pass

    async def __aenter__(self):
        try:
            await self.start()
        except:
            await self.stop()
            raise
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def whoami(self, verbose = True):
        r = self.read(reg = _REG_WHOAMI)
        if verbose:
            print('WHOAMI:{:02X}'.format(r))
        return r

    def read(self, reg):
        tx = bytes([
            0x7f & reg,  # reg
            0x00,         # dummy
            0x00,         # result
        ])
        rx = bytearray(len(tx))
        try:
            self.cs(0)
            self.spi.write_readinto(tx, rx)
        finally:
            self.cs(1)
        return rx[2]

    def write(self, reg, v):
        tx = bytes([0x80 | reg, v])
        try:
            self.cs(0)
            self.spi.write(tx)
        finally:
            self.cs(1)

# async def main():
    # # read type
    # r = read(reg = _REG_WHOAMI)
    # print('WHOAMI:{:02X}'.format(r))

    # r = write_reg(reg = _REG_BASIC_CFG, 
                  # v   = _PIXEL_FORMAT_JPG)
    # print('BASIC_CFG:{:02X}'.format(r))

    # r = write_reg(reg = _REG_RESOLUTION, 
                  # v   = _RESOLUTION_640X480)
    # print('REG_RESOLUTION:{:02X}'.format(r))

    # # clear fifo flag
    # write(reg = _REG_MEMORY_CTRL,
          # v   = _CLEAR_MEMORY)

    # # start capture
    # write(reg = _REG_MEMORY_CTRL,
          # v   = _START_PICTURES)

    # # wait
    # done = False
    # for x in range(10):
        # r = read(reg = ARDUCHIP_TRIG)
        # print('ARDUCHIP_TRIG:{:02X}'.format(r))
        # if r & CAP_DONE_MASK:
            # break
        # await asyncio.sleep_ms(200)



