

import asyncio
from micropython import const
import binascii

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
_RESOLUTION_320X240 = const(0X01) # CAM_IMAGE_MODE_QVGA
_RESOLUTION_640X480 = const(0X02) # CAM_IMAGE_MODE_VGA
_RESOLUTION_800X600 = const(0x03) # CAM_IMAGE_MODE_SVGA

# video mode
_CAM_SET_VIDEO_MODE   = const(0x80)
_CAM_VIDEO_MODE_0 = const(1) # 320x240 
_CAM_VIDEO_MODE_1 = const(2) # 640x480 

# pixel format
_CAM_REG_FORMAT = const(0x20)
_CAM_IMAGE_PIX_FMT_JPG    = const(0x01)
_CAM_IMAGE_PIX_FMT_RGB565 = const(0x02) # https://rgbcolorpicker.com/565
_CAM_IMAGE_PIX_FMT_YUV = const(0x03)

# color
_CAM_REG_COLOR_EFFECT_CONTROL = const(0x27)
_SPECIAL_NORMAL = const(0x00)

# brightness
_CAM_REG_BRIGHTNESS_CONTROL = const(0x22)
_BRIGHTNESS_DEFAULT = const(0)
_BRIGHTNESS_PLUS_4 = const(7)

# contrast
_CAM_REG_CONTRAST_CONTROL = const(0x23)
_CONTRAST_DEFAULT = const(0)
_CONTRAST_MINUS_3 = const(6)


class ArduCam():
    def __init__(self, spi,
                       cs,
                       ):
		self.spi = spi
		self.cs  = cs

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

        # "cameraBegin"
        # writeReg(camera, CAM_REG_DEBUG_DEVICE_ADDRESS, camera->myCameraInfo.deviceAddress);
        # self.write(_CAM_REG_DEBUG_DEVICE_ADDRESS, _CAM_DEVICE_ADDRESS)

    async def whoami(self):
        r = self.read(reg = _CAM_REG_SENSOR_ID)
        if r == _SENSOR_5MP_1:
            return b'5MP'
        elif r == _SENSOR_3MP_1:
            return b'3MP'
        elif r == _SENSOR_3MP_2:
            return b'5MP'
        elif r == _SENSOR_3MP_2:
            return b'3MP'
        return r

    async def reset(self):
        # writeReg(camera, CAM_REG_SENSOR_RESET, CAM_SENSOR_RESET_ENABLE);
        self.write(_CAM_REG_SENSOR_RESET, _CAM_SENSOR_RESET_ENABLE)

    async def capture(self):

        # filter color (special)
        self.write(_CAM_REG_COLOR_EFFECT_CONTROL, _SPECIAL_NORMAL)

        # brightness
        self.write(_CAM_REG_BRIGHTNESS_CONTROL, _BRIGHTNESS_PLUS_4)

        # contrast
        self.write(_CAM_REG_CONTRAST_CONTROL, _CONTRAST_MINUS_3)

        # writeReg(camera, CAM_REG_FORMAT, pixel_format); // set the data format
        # self.write(_CAM_REG_FORMAT, _CAM_IMAGE_PIX_FMT_RGB565)
        self.write(_CAM_REG_FORMAT, _CAM_IMAGE_PIX_FMT_JPG)

        # writeReg(camera, CAM_REG_CAPTURE_RESOLUTION, CAM_SET_CAPTURE_MODE | mode);
        self.write(_CAM_REG_CAPTURE_RESOLUTION, _RESOLUTION_320X240 | _CAM_SET_CAPTURE_MODE)
        # self.write(_CAM_REG_CAPTURE_RESOLUTION, _RESOLUTION_640X480 | _CAM_SET_CAPTURE_MODE)

        # void cameraSetCapture
        # clear fifo
        # writeReg(camera, ARDUCHIP_FIFO, FIFO_CLEAR_ID_MASK);
        self.write(_ARDUCHIP_FIFO, _FIFO_CLEAR_ID_MASK)

        # start capture
        # writeReg(camera, ARDUCHIP_FIFO, FIFO_START_MASK);
        self.write(_ARDUCHIP_FIFO, _FIFO_START_MASK)

        # wait
        # while (getBit(camera, ARDUCHIP_TRIG, CAP_DONE_MASK) == 0)
            # ;
        for x in range(30):
            r = self.read(_ARDUCHIP_TRIG)
            print('0x{:02X} {}'.format(r, r & _CAP_DONE_MASK))
            if r & _CAP_DONE_MASK:
                break
            await asyncio.sleep_ms(100)

        # camera->receivedLength = readFifoLength(camera);
        # camera->totalLength    = camera->receivedLength;
        # camera->burstFirstFlag = 0;
        read_size = self.read_fifo_length()
        print('read_size:{}'.format(read_size))

        raw = bytearray(read_size)
        mv = memoryview(raw)
        b_burst_read = bytes([_BURST_FIFO_READ])
        try:
            self.cs(0)
            for i in range(0, read_size, _FIFO_BURST_READ_MAX_LENGTH):
                self.spi.write(b_burst_read)
                if i == 0:
                    # first burst read needs dummy byte after command
                    # https://www.arducam.com/downloads/datasheet/Arducam_MEGA_SPI_Camera_Application_Note.pdf
                    self.spi.write(b'0')
                self.spi.readinto(mv[i:i+_FIFO_BURST_READ_MAX_LENGTH], 0x00)
        finally:
            self.cs(1)
        print('burst read: {}'.format(len(raw)))

        with open('image.txt', 'w') as f:
            f.write(binascii.b2a_base64(raw))

        # TODO
        # https://github.com/ArduCAM/Arducam_Mega/blob/main/examples/ArduinoUNO/capture2SD/capture2SD.ino

    def read_fifo_length(self):
        # uint32_t cameraReadFifoLength(ArducamCamera* camera)
        # uint32_t len1, len2, len3, length = 0;
        # len1   = readReg(camera, FIFO_SIZE1);
        # len2   = readReg(camera, FIFO_SIZE2);
        # len3   = readReg(camera, FIFO_SIZE3);
        # length = ((len3 << 16) | (len2 << 8) | len1) & 0xffffff;
        # return length;
        bs = bytearray(4)
        bs[0] = self.read(_FIFO_SIZE1)
        bs[1] = self.read(_FIFO_SIZE2)
        bs[2] = self.read(_FIFO_SIZE3)
        print('{} 0x{:02x} 0x{:02x} 0x{:02x}  little:{} big:{}'.format(bs, bs[2], bs[1], bs[0], int.from_bytes(bs, 'little'), int.from_bytes(bs, 'big')))
        return int.from_bytes(bs, 'little')

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



