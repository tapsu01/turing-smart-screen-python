# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Turing Smart Screen rev. A 3.5" driven over raw USB bulk transfers instead of the CDC serial port.
#
# On macOS the CDC ACM serial device (/dev/cu.usbmodem...) re-packs USB transfers arbitrarily. The panel firmware is
# transfer-oriented: it reads a command from the start of a USB transfer and then counts exactly w*h*2 pixel bytes
# after a DISPLAY_BITMAP header. Once a single byte is mis-framed, every following command is eaten as pixel data and
# the screen stays black/corrupted until it is power-cycled.
# See https://github.com/mathoudebine/turing-smart-screen-python/issues/7
#
# This backend writes to the bulk OUT endpoint with libusb, with one transfer per command and pixel data in 64-byte
# aligned transfers, and never lets another request be queued between a bitmap header and its pixel data.

import platform
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

import usb.backend.libusb1
import usb.core
import usb.util

from library.lcd.lcd_comm_rev_a import *

VENDOR_ID = 0x1A86
PRODUCT_ID = 0x5722
DATA_INTERFACE = 1
EP_OUT = 0x03
EP_IN = 0x82

USB_OPEN_ATTEMPTS = 10
USB_OPEN_RETRY_DELAY = 1  # seconds
USB_WRITE_TIMEOUT = 5000  # ms
USB_READ_TIMEOUT = 500  # ms
PIXEL_CHUNK_SIZE = 64 * 64  # bytes, must stay a multiple of the 64-byte bulk packet size

# Name of the libusb library shipped inside the macOS app bundle (see turing-screen-macos.spec)
BUNDLED_LIBUSB = "libusb-1.0.0.dylib"


@lru_cache(maxsize=1)
def _usb_backend():
    """libusb backend: the library shipped in a frozen build if any, otherwise pyusb's own system lookup"""
    bundled = Path(getattr(sys, "_MEIPASS", "")) / BUNDLED_LIBUSB
    if getattr(sys, "frozen", False) and bundled.is_file():
        return usb.backend.libusb1.get_backend(find_library=lambda name: str(bundled))
    return None


def _find_display():
    return usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID, backend=_usb_backend())


def is_usb_display_available() -> bool:
    try:
        return _find_display() is not None
    except (usb.core.NoBackendError, usb.core.USBError, ValueError):
        return False


class LcdCommRevAUsb(LcdCommRevA):
    def __init__(self, display_width: int = 320, display_height: int = 480,
                 update_queue: Optional[queue.Queue] = None):
        logger.debug("HW revision: A (raw USB bulk transfers)")
        self.usb_dev = None
        LcdComm.__init__(self, "AUTO", display_width, display_height, update_queue)
        self.openSerial()

    # The "serial" methods below keep the names used by LcdComm / LcdCommRevA so that Reset(), _hello()... work as is

    def openSerial(self):
        for attempt in range(1, USB_OPEN_ATTEMPTS + 1):
            try:
                dev = _find_display()
                if dev is None:
                    raise usb.core.USBError("display not found")
                try:
                    dev.set_configuration()
                except usb.core.USBError:
                    pass  # Already configured
                usb.util.claim_interface(dev, DATA_INTERFACE)
                self.usb_dev = dev
                logger.debug("USB display opened (bulk OUT 0x%02x)" % EP_OUT)
                return
            except usb.core.USBError as e:
                logger.warning(
                    f"Cannot open USB display: {e} - retrying ({attempt}/{USB_OPEN_ATTEMPTS}). "
                    f"Make sure no other program (another main.py instance...) is using the screen")
                time.sleep(USB_OPEN_RETRY_DELAY)

        logger.error(f"Cannot open USB display after {USB_OPEN_ATTEMPTS} attempts")
        try:
            sys.exit(0)
        except:
            os._exit(0)

    def closeSerial(self):
        if self.usb_dev is not None:
            try:
                usb.util.release_interface(self.usb_dev, DATA_INTERFACE)
            except usb.core.USBError:
                pass
            usb.util.dispose_resources(self.usb_dev)
            self.usb_dev = None

    def serial_write(self, data: bytes):
        assert self.usb_dev is not None
        self.usb_dev.write(EP_OUT, data, timeout=USB_WRITE_TIMEOUT)

    def serial_read(self, size: int) -> bytes:
        assert self.usb_dev is not None
        try:
            return bytes(self.usb_dev.read(EP_IN, size, timeout=USB_READ_TIMEOUT))
        except usb.core.USBTimeoutError:
            return b''

    def serial_readall(self) -> bytes:
        return self.serial_read(64)

    def serial_flush_input(self):
        if self.usb_dev is not None:
            while self.serial_read(64):
                pass

    def WriteLine(self, line: bytes):
        # One call = one USB transfer: commands never share a transfer with pixel data
        try:
            self.serial_write(line)
        except usb.core.USBError as e:
            logger.error(f"USBError: failed to send data to device ({e}). Reopening USB device before retrying once.")
            self.closeSerial()
            time.sleep(1)
            self.openSerial()
            self.serial_write(line)

    def SetOrientation(self, orientation: Orientation = Orientation.PORTRAIT):
        self.orientation = orientation
        width = self.get_width()
        height = self.get_height()
        # 6-byte command header (x = y = ex = ey = 0) + orientation + width/height big-endian: 11 bytes, not 16
        byteBuffer = bytearray(11)
        byteBuffer[5] = Command.SET_ORIENTATION
        byteBuffer[6] = (orientation + 100)
        byteBuffer[7] = (width >> 8)
        byteBuffer[8] = (width & 255)
        byteBuffer[9] = (height >> 8)
        byteBuffer[10] = (height & 255)

        # Go through the queue like other commands, so it can never be written in the middle of a bitmap
        if not self.update_queue:
            self.WriteData(byteBuffer)
        else:
            with self.update_queue_mutex:
                self.update_queue.put((self.WriteData, [byteBuffer]))

    def DisplayPILImage(
            self,
            image: Image.Image,
            x: int = 0, y: int = 0,
            image_width: int = 0,
            image_height: int = 0
    ):
        width, height = self.get_width(), self.get_height()

        if not image_height:
            image_height = image.size[1]
        if not image_width:
            image_width = image.size[0]

        if x + image_width > width:
            image_width = width - x
        if y + image_height > height:
            image_height = height - y

        if image_width != image.size[0] or image_height != image.size[1]:
            image = image.crop((0, 0, image_width, image_height))

        assert x <= width, 'Image X coordinate must be <= display width'
        assert y <= height, 'Image Y coordinate must be <= display height'
        assert image_height > 0, 'Image height must be > 0'
        assert image_width > 0, 'Image width must be > 0'

        (x0, y0) = (x, y)
        (x1, y1) = (x + image_width - 1, y + image_height - 1)

        header = bytearray(6)
        header[0] = (x0 >> 2)
        header[1] = (((x0 & 3) << 6) + (y0 >> 4))
        header[2] = (((y0 & 15) << 4) + (x1 >> 6))
        header[3] = (((x1 & 63) << 2) + (y1 >> 8))
        header[4] = (y1 & 255)
        header[5] = Command.DISPLAY_BITMAP

        rgb565le = image_to_RGB565(image, "little")

        if not self.update_queue:
            self.WriteData(header)
            for chunk in chunked(rgb565le, PIXEL_CHUNK_SIZE):
                self.WriteLine(chunk)
        else:
            # Header and pixel data are queued under the same lock: no other request can slip in-between
            with self.update_queue_mutex:
                self.update_queue.put((self.WriteData, [header]))
                for chunk in chunked(rgb565le, PIXEL_CHUNK_SIZE):
                    self.update_queue.put((self.WriteLine, [chunk]))


def create_lcd_rev_a(com_port: str = "AUTO", update_queue: Optional[queue.Queue] = None,
                     raw_usb: bool = True) -> LcdCommRevA:
    # macOS serial driver corrupts the rev. A stream: use raw USB bulk transfers when possible (see issue #7)
    if raw_usb and platform.system() == "Darwin" and is_usb_display_available():
        return LcdCommRevAUsb(update_queue=update_queue)
    return LcdCommRevA(com_port=com_port, update_queue=update_queue)
