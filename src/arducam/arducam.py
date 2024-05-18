

import asyncio
from micropython import const

import time
from machine import Pin
import binascii
import os

# CAMERA SENSOR ID
_CAM_REG_SENSOR_ID = const(0x40)
_SENSOR_5MP_1 = const(0x81)
_SENSOR_3MP_1 = const(0x82)
_SENSOR_5MP_2 = const(0x83)
_SENSOR_3MP_2 = const(0x84)

# CAMERA RESET REG
_CAM_REG_SENSOR_RESET  = const(0X07)
_CAM_SENSOR_RESET_ENABLE = const(0x40)
_CAM_REG_SENSOR_STATE = const(0x44)
_CAM_REG_SENSOR_STATE_IDLE = const(0x02)

_CAM_REG_DEBUG_DEVICE_ADDRESS = const(0x0A)
_CAM_DEVICE_ADDRESS = const(0x78)

_ARDUCHIP_FIFO = const(0x04)
_FIFO_CLEAR_ID_MASK = const(0x01)
_FIFO_START_MASK = const(0x02)

# trigger source
_ARDUCHIP_TRIG = const(0x44)
_VSYNC_MASK = const(0x01)
_SHUTTER_MASK = const(0x02)
_CAP_DONE_MASK = const(0x04)

# fifo
_SINGLE_FIFO_READ = const(0x3D)
_BURST_FIFO_READ = const(0X3C)
_FIFO_BURST_READ_MAX_LENGTH = const(255)
_FIFO_SIZE1 = const(0x45)
_FIFO_SIZE2 = const(0x46)
_FIFO_SIZE3 = const(0x47)

# capture mode
_CAM_SET_CAPTURE_MODE = const(0)
_CAM_REG_CAPTURE_RESOLUTION = const(0x21)
RESOLUTION_320X240 = const(0X01) # CAM_IMAGE_MODE_QVGA
RESOLUTION_640X480 = const(0X02) # CAM_IMAGE_MODE_VGA
RESOLUTION_800X600 = const(0x03) # CAM_IMAGE_MODE_SVGA
RESOLUTION_96X96 = const(0X0a)
RESOLUTION_128X128 = const(0X0b)
RESOLUTION_320X320 = const(0X0c)

# video mode
_CAM_SET_VIDEO_MODE   = const(0x80)
_CAM_VIDEO_MODE_0 = const(1) # 320x240 
_CAM_VIDEO_MODE_1 = const(2) # 640x480 

# pixel format
_CAM_REG_FORMAT = const(0x20)
CAM_IMAGE_PIX_FMT_JPG    = const(0x01)
CAM_IMAGE_PIX_FMT_RGB565 = const(0x02) # https://rgbcolorpicker.com/565
CAM_IMAGE_PIX_FMT_YUV = const(0x03)

# color
_CAM_REG_COLOR_EFFECT_CONTROL = const(0x27)
SPECIAL_NORMAL = const(0x00)

# brightness
_CAM_REG_BRIGHTNESS_CONTROL = const(0x22)
BRIGHTNESS_DEFAULT = const(0)

# contrast
_CAM_REG_CONTRAST_CONTROL = const(0x23)
CONTRAST_DEFAULT = const(0)

# white balance, gain, exposure
_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL = const(0X30)
_SET_WHILEBALANCE                           = const(0X02)
_SET_EXPOSURE                               = const(0X01)
_SET_GAIN                                   = const(0X00)
_SET_AUTO_ON                                = const(0x80)
_SET_AUTO_OFF                               = const(0x00)
_CAM_REG_WHILEBALANCE_MODE_CONTROL          = const(0X26)
_CAM_REG_MANUAL_GAIN_BIT_9_8                = const(0X31)
_CAM_REG_MANUAL_GAIN_BIT_7_0                = const(0X32)
_CAM_REG_MANUAL_EXPOSURE_BIT_19_16          = const(0X33)
_CAM_REG_MANUAL_EXPOSURE_BIT_15_8           = const(0X34)
_CAM_REG_MANUAL_EXPOSURE_BIT_7_0            = const(0X35)
CAM_WHITE_BALANCE_MODE_DEFAULT             = const(0x00) # green?
CAM_WHITE_BALANCE_MODE_SUNNY               = const(0x01)
CAM_WHITE_BALANCE_MODE_OFFICE              = const(0x02)
CAM_WHITE_BALANCE_MODE_CLOUDY              = const(0x03)
CAM_WHITE_BALANCE_MODE_HOME                = const(0x04)


class ArduCam():
    def __init__(self, spi,
                       cs,
                       ):
        self.spi = spi
        self.cs  = cs

        # re-use this scratch bytearray to avoid extraneous allocations in read/write functions
        self.scratch  = memoryview(bytearray(8))

        self.is_3mp = False

    async def start(self, timeout = 2000):
        await self.connect()

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

    async def connect(self, timeout = 2000):
        t = time.ticks_ms()
        while True:
            r = await self.whoami()
            # print('0x{:02X}'.format(r))
            if r != 0 and r != 0xff:
                break
            delta = time.ticks_diff(time.ticks_ms(), t)
            if delta > timeout:
                raise Exception('timed out connecting to ArduCam : 0x{:02X}'.format(r))
            await asyncio.sleep_ms(10)
        print('connected to arducam {}'.format(r))
        await self.write(_CAM_REG_SENSOR_RESET, _CAM_SENSOR_RESET_ENABLE)
        await self.write(_CAM_REG_DEBUG_DEVICE_ADDRESS, _CAM_DEVICE_ADDRESS)


    async def whoami(self):
        r = await self.read(reg = _CAM_REG_SENSOR_ID)
        if r == _SENSOR_5MP_1:
            return b'5MP'
        elif r == _SENSOR_3MP_1:
            self.is_3mp = True
            return b'3MP'
        elif r == _SENSOR_3MP_2:
            return b'5MP'
        elif r == _SENSOR_3MP_2:
            self.is_3mp = True
            return b'3MP'
        return r

    async def configure(self, resolution   = RESOLUTION_96X96,
                              wb_is_auto   = True,
                              wb_mode      = CAM_WHITE_BALANCE_MODE_HOME,
                              agc_is_auto  = False,
                              agc          = 10,
                              exposure_is_auto = False,
                              exposure     = 1200,
                              color        = SPECIAL_NORMAL,
                              brightness   = BRIGHTNESS_DEFAULT,
                              contrast     = CONTRAST_DEFAULT,
                              pixel_format = CAM_IMAGE_PIX_FMT_JPG,
                              ):
        await self.write(_CAM_REG_CAPTURE_RESOLUTION, resolution | _CAM_SET_CAPTURE_MODE)

        # white balance
        if wb_is_auto:
            await self.write(_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL, _SET_AUTO_ON | _SET_WHILEBALANCE)
            await self.write(_CAM_REG_WHILEBALANCE_MODE_CONTROL, wb_mode)
        else:
            await self.write(_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL, _SET_AUTO_OFF | _SET_WHILEBALANCE)

        # AGC (ISO GAIN)
        if agc_is_auto:
            await self.write(_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL, _SET_AUTO_ON  | _SET_GAIN)
        else:
            await self.write(_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL, _SET_AUTO_OFF  | _SET_GAIN)
            if self.is_3mp:
                agcs = [0x00, 0x10, 0x18, 0x30, 0x34, 0x38, 0x3b, 0x3f, 0x72, 0x74, 0x76,
                                            0x78, 0x7a, 0x7c, 0x7e, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6,
                                            0xf7, 0xf8, 0xf9, 0xfa, 0xfb, 0xfc, 0xfd, 0xfe, 0xff]
                agc = agcs[agc]
            await self.write(_CAM_REG_MANUAL_GAIN_BIT_9_8, (agc >> 8)&0xff)
            await self.write(_CAM_REG_MANUAL_GAIN_BIT_7_0, agc & 0xff)

        # exposure 100~1400
        if exposure_is_auto:
            await self.write(_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL, _SET_AUTO_ON  | _SET_EXPOSURE)
        else:
            await self.write(_CAM_REG_EXPOSURE_GAIN_WHILEBALANCE_CONTROL, _SET_AUTO_OFF  | _SET_EXPOSURE)
            await self.write(_CAM_REG_MANUAL_EXPOSURE_BIT_19_16, (exposure >> 16)&0xff)
            await self.write(_CAM_REG_MANUAL_EXPOSURE_BIT_15_8, (exposure>>8) & 0xff)
            await self.write(_CAM_REG_MANUAL_EXPOSURE_BIT_7_0, exposure & 0xff)

        # filter color (special)
        await self.write(_CAM_REG_COLOR_EFFECT_CONTROL, color)

        # brightness
        await self.write(_CAM_REG_BRIGHTNESS_CONTROL, brightness)

        # contrast
        await self.write(_CAM_REG_CONTRAST_CONTROL, contrast)

        # writeReg(camera, CAM_REG_FORMAT, pixel_format); // set the data format
        await self.write(_CAM_REG_FORMAT, pixel_format)

    async def capture(self):
        await self.write(_ARDUCHIP_FIFO, _FIFO_CLEAR_ID_MASK)
        await self.write(_ARDUCHIP_FIFO, _FIFO_START_MASK)
        for x in range(30):
            r = await self.read(_ARDUCHIP_TRIG)
            # print('0x{:02X} {}'.format(r, r & _CAP_DONE_MASK))
            if r & _CAP_DONE_MASK:
                break
            await asyncio.sleep_ms(100)

        read_size = await self.read_fifo_length()
        # print('read_size:{}'.format(read_size))

        raw = bytearray(read_size)
        mv = memoryview(raw)
        b_burst_read = bytes([_BURST_FIFO_READ])
        for i in range(0, read_size, _FIFO_BURST_READ_MAX_LENGTH):
            try:
                self.cs(0)
                self.spi.write(b_burst_read)
                if i == 0:
                    self.spi.write(b'0') # dummy write on first according to spec sheet
                self.spi.readinto(mv[i:i+_FIFO_BURST_READ_MAX_LENGTH], 0x00)
            finally:
                self.cs(1)
        # print('burst read: {}'.format(len(raw)))
        # self.print_bytes(raw)

        start_idx = raw.find(b'\xff\xd8') # jpg start flag
        stop_idx = raw.find(b'\xff\xd9')  # jpg stop flag
        stop_idx += 2
        # print('image {}:{}'.format(start_idx, stop_idx))

        jpg_mv = mv[start_idx:stop_idx]
        # self.print_bytes(jpg)
        return jpg_mv

        # with open('image.txt', 'w') as f:
            # f.write(binascii.b2a_base64(jpg).decode())

    def print_bytes(self, mv):
        stride = 64 
        for i in range(0,len(mv), stride):
            chunk = mv[i:i+stride]
            print('{:<10} '.format(i), end='')
            for j in range(len(chunk)):
                print('{:02X} '.format(chunk[j]), end='')
                # if chunk[j] == 0xff:
                    # print('*')
            print()

    async def read_fifo_length(self):
        bs = self.scratch[3:7] # read uses lower scratch bytes
        bs[0] = await self.read(_FIFO_SIZE1)
        bs[1] = await self.read(_FIFO_SIZE2)
        bs[2] = await self.read(_FIFO_SIZE3)
        # print('{} 0x{:02x} 0x{:02x} 0x{:02x}  little:{} big:{}'.format(bs, bs[2], bs[1], bs[0], int.from_bytes(bs, 'little'), int.from_bytes(bs, 'big')))
        return int.from_bytes(bs, 'little')

    async def read(self, reg, dowait=True):
        rxtx = self.scratch[0:3]
        rxtx[0] = 0x7f & reg
        rxtx[1] = 0
        rxtx[2] = 0
        try:
            self.cs(0)
            self.spi.write_readinto(rxtx, rxtx)
            r = rxtx[2]
        finally:
            self.cs(1)
        if dowait:
            await self.waitidle()
        return r

    async def write(self, reg, v):
        tx = self.scratch[:2]
        tx[0] = 0x80 | reg
        tx[1] = v
        try:
            self.cs(0)
            self.spi.write(tx)
        finally:
            self.cs(1)
        await self.waitidle()

    async def waitidle(self):
        for x in range(500):
            r = await self.read(_CAM_REG_SENSOR_STATE, dowait=False) # this is the wait function!
            if r&0x03 == _CAM_REG_SENSOR_STATE_IDLE:
                break
            await asyncio.sleep_ms(2)
         


