
"""
PICO-Cam-A / HM01B0 / RP2040
MicroPython camera and LCD driver.

Camera:
    HM01B0, PIO + DMA
    324 x 324 grayscale buffer

LCD:
    ST7789, 240 x 135, RGB565

Based on the working capture configuration
adapted from:
https://github.com/fhswf/PICO-CAM-A

WARNING:
Uses experimental RP2040 overclock at 250 MHz.
"""

import machine
from machine import Pin, SoftI2C, SPI
import rp2
import time
import os

WIDTH = 324
HEIGHT = 324
FRAME_BYTES = WIDTH * HEIGHT

LCD_WIDTH = 240
LCD_HEIGHT = 135


# -------------------------------------------------
# HM01B0 INITIALIZATION
# -------------------------------------------------

REGS = (
    (0x0103, 0x00), (0x0100, 0x00),
    (0x1003, 0x08), (0x1007, 0x08),
    (0x3044, 0x0A), (0x3045, 0x00),
    (0x3047, 0x0A), (0x3050, 0xC0),
    (0x3051, 0x42), (0x3052, 0x50),
    (0x3053, 0x00), (0x3054, 0x03),
    (0x3055, 0xF7), (0x3056, 0xF8),
    (0x3057, 0x29), (0x3058, 0x1F),
    (0x3059, 0x1E), (0x3064, 0x00),
    (0x3065, 0x04), (0x1000, 0x43),
    (0x1001, 0x40), (0x1002, 0x32),
    (0x0350, 0x7F), (0x1006, 0x01),
    (0x1008, 0x03), (0x1009, 0xA0),
    (0x100A, 0x60), (0x100B, 0x10),
    (0x100C, 0x40), (0x3022, 0x01),
    (0x1012, 0x01), (0x2000, 0x07),
    (0x2003, 0x00), (0x2004, 0x1C),
    (0x2007, 0x00), (0x2008, 0x58),
    (0x200B, 0x00), (0x200C, 0x7A),
    (0x200F, 0x00), (0x2010, 0xB8),
    (0x2013, 0x00), (0x2014, 0x58),
    (0x2017, 0x00), (0x2018, 0x9B),
    (0x2100, 0x01), (0x2101, 0x5F),
    (0x2102, 0x0A), (0x2103, 0x03),
    (0x2104, 0x05), (0x2105, 0x02),
    (0x2106, 0x14), (0x2107, 0x02),
    (0x2108, 0x03), (0x2109, 0x03),
    (0x210A, 0x00), (0x210B, 0x80),
    (0x210C, 0x40), (0x210D, 0x20),
    (0x210E, 0x03), (0x210F, 0x00),
    (0x2110, 0x85), (0x2111, 0x00),
    (0x2112, 0xA0), (0x2150, 0x03),
    (0x0340, 0x01), (0x0341, 0x7A),
    (0x0342, 0x01), (0x0343, 0x77),
    (0x3010, 0x00), (0x0383, 0x01),
    (0x0387, 0x01), (0x0390, 0x00),
    (0x3011, 0x70), (0x3059, 0x22),
    (0x3060, 0x30), (0x0101, 0x01),
    (0x0104, 0x01), (0x0100, 0x01),
)


# -------------------------------------------------
# PIO SERIAL CAMERA RECEIVER
# -------------------------------------------------

@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopush=True,
    push_thresh=8,
    fifo_join=rp2.PIO.JOIN_RX
)
def camera_pio():

    # Synchronize at frame boundary.
    wait(0, gpio, 16)
    wait(1, gpio, 16)

    wrap_target()

    # Relative to GP6:
    # HREF = GP15
    # PCLK = GP14

    wait(1, pin, 9)
    wait(1, pin, 8)

    in_(pins, 1)

    wait(0, pin, 8)

    wrap()


# -------------------------------------------------
# CAMERA DRIVER
# -------------------------------------------------

class PicoCam:

    ADDRESS = 0x24

    def __init__(self):

        if not hasattr(rp2, "DMA"):
            raise RuntimeError(
                "MicroPython requires rp2.DMA"
            )

        self.i2c = None
        self.sm = None
        self.dma = None

        self.frame = bytearray(FRAME_BYTES)

        self.valid = False
        self.pattern = False
        self.elapsed_ms = 0

    def read(self, register):

        return self.i2c.readfrom_mem(
            self.ADDRESS,
            register,
            1,
            addrsize=16
        )[0]

    def write(self, register, value):

        self.i2c.writeto_mem(
            self.ADDRESS,
            register,
            bytes((value & 255,)),
            addrsize=16
        )

    def get_id(self):

        return (
            (self.read(0x0000) << 8)
            | self.read(0x0001)
        )

    def init(self):

        if machine.freq() != 250_000_000:
            raise RuntimeError(
                "CPU must run at 250 MHz"
            )

        if self.dma is not None:
            raise RuntimeError(
                "Camera already initialized"
            )

        try:

            for number in (6, 14, 15, 16):
                Pin(number, Pin.IN, pull=None)

            self.i2c = SoftI2C(
                sda=Pin(4),
                scl=Pin(5),
                freq=100000
            )

            model = self.get_id()

            print(
                "Sensor: 0x%04X" % model
            )

            if model != 0x01B0:
                raise OSError(
                    "HM01B0 not detected"
                )

            self.write(0x0103, 0x01)
            time.sleep_ms(100)

            for register, value in REGS:

                if (
                    register == 0x0100
                    and value == 1
                ):
                    continue

                self.write(register, value)
                time.sleep_ms(10)

            self.write(0x0601, 0x00)

            for register, expected in (
                (0x3010, 0x00),
                (0x3059, 0x22),
                (0x3060, 0x30)
            ):

                actual = self.read(register)

                print(
                    "Register 0x%04X: 0x%02X" %
                    (register, actual)
                )

                if actual != expected:
                    raise OSError(
                        "Camera configuration mismatch"
                    )

            self.sm = rp2.StateMachine(0)
            self.dma = rp2.DMA()

            print(
                "DMA channel:",
                self.dma.channel
            )

            print("Camera ready")

            return self

        except BaseException:
            self.close()
            raise

    def start(self):

        self.write(0x0100, 0x01)

    def stop(self):

        if self.i2c is not None:
            self.write(0x0100, 0x00)

    def test_pattern(self, enabled):

        self.stop()

        self.write(
            0x0601,
            0x01 if enabled else 0x00
        )

        self.pattern = bool(enabled)
        self.valid = False

    def capture(
        self,
        settle_ms=0,
        timeout_ms=3000
    ):

        if self.dma is None or self.sm is None:
            raise RuntimeError(
                "Initialize camera first"
            )

        if machine.freq() != 250_000_000:
            raise RuntimeError(
                "CPU frequency changed"
            )

        self.valid = False

        self.sm.active(0)
        self.dma.active(0)

        try:

            self.start()

            if settle_ms:
                time.sleep_ms(settle_ms)

            self.sm.init(
                camera_pio,
                freq=machine.freq(),
                in_base=Pin(6, Pin.IN)
            )

            while self.sm.rx_fifo():
                self.sm.get()

            ctrl = self.dma.pack_ctrl(
                size=0,
                inc_read=False,
                inc_write=True,
                treq_sel=4,
                chain_to=self.dma.channel,
                high_pri=True
            )

            start = time.ticks_ms()

            self.dma.config(
                read=self.sm,
                write=self.frame,
                count=FRAME_BYTES,
                ctrl=ctrl,
                trigger=True
            )

            self.sm.active(1)

            while self.dma.active():

                if self.dma.ctrl & (
                    (1 << 29) | (1 << 30)
                ):
                    raise OSError(
                        "DMA bus error"
                    )

                if time.ticks_diff(
                    time.ticks_ms(),
                    start
                ) >= timeout_ms:

                    raise OSError(
                        "DMA timeout, remaining: %d" %
                        self.dma.count
                    )

                time.sleep_ms(1)

            self.sm.active(0)

            if (
                self.dma.count != 0
                or self.dma.ctrl & (
                    (1 << 29) | (1 << 30)
                )
            ):
                raise OSError(
                    "Incomplete DMA transfer"
                )

            self.elapsed_ms = time.ticks_diff(
                time.ticks_ms(),
                start
            )

            self.valid = True

            return self.frame

        finally:

            self.sm.active(0)
            self.dma.active(0)
            self.stop()

    def save(self):

        if not self.valid:
            raise RuntimeError(
                "No valid frame captured"
            )

        filename = None

        for number in range(1000):

            candidate = (
                "/captura_%03d.pgm" % number
            )

            try:
                os.stat(candidate)

            except OSError as error:

                if error.args[0] != 2:
                    raise

                filename = candidate
                break

        if filename is None:
            raise OSError(
                "No free filename"
            )

        header = b"P5\n324 324\n255\n"

        try:

            with open(filename, "wb") as file:

                if file.write(header) != len(header):
                    raise OSError(
                        "Header write failed"
                    )

                if (
                    file.write(self.frame)
                    != FRAME_BYTES
                ):
                    raise OSError(
                        "Frame write failed"
                    )

            if hasattr(os, "sync"):
                os.sync()

        except BaseException:

            try:
                os.remove(filename)
            except OSError:
                pass

            raise

        return filename

    def close(self):

        if self.sm is not None:
            self.sm.active(0)

        if self.dma is not None:
            self.dma.close()
            self.dma = None

        if self.i2c is not None:

            try:
                self.stop()
                self.write(0x0601, 0)
            except OSError:
                pass

        self.valid = False


# -------------------------------------------------
# LCD DRIVER
# -------------------------------------------------

class CameraLCD:

    def __init__(self):

        self.cs = Pin(13, Pin.OUT, value=1)
        self.dc = Pin(9, Pin.OUT, value=0)
        self.rst = Pin(7, Pin.OUT, value=1)

        self.spi = SPI(
            1,
            baudrate=40_000_000,
            polarity=0,
            phase=0,
            sck=Pin(10),
            mosi=Pin(11)
        )

        self.row = bytearray(480)
        self.gray = bytearray(512)

        for n in range(256):

            color = (
                ((n & 0xF8) << 8)
                | ((n & 0xFC) << 3)
                | (n >> 3)
            )

            self.gray[n * 2] = color >> 8
            self.gray[n * 2 + 1] = color & 255

        self._view_mode = None
        self._view_x = None

    def command(self, command, data=None):

        self.cs(0)

        try:

            self.dc(0)
            self.spi.write(bytes((command,)))

            if data is not None:
                self.dc(1)
                self.spi.write(data)

        finally:
            self.cs(1)

    def init(self):

        self.rst(0)
        time.sleep_ms(100)

        self.rst(1)
        time.sleep_ms(100)

        self.command(0x36, b"\x70")

        sequence = (
            (0x3A, b"\x05"),
            (0xB2, b"\x0c\x0c\x00\x33\x33"),
            (0xB7, b"\x35"),
            (0xBB, b"\x19"),
            (0xC0, b"\x2c"),
            (0xC2, b"\x01"),
            (0xC3, b"\x12"),
            (0xC4, b"\x20"),
            (0xC6, b"\x0f"),
            (0xD0, b"\xa4\xa1"),
            (
                0xE0,
                b"\xd0\x04\x0d\x11\x13\x2b\x3f"
                b"\x54\x4c\x18\x0d\x0b\x1f\x23"
            ),
            (
                0xE1,
                b"\xd0\x04\x0c\x11\x13\x2c\x3f"
                b"\x44\x51\x2f\x1f\x1f\x20\x23"
            )
        )

        for command, data in sequence:
            self.command(command, data)

        self.command(0x21)
        self.command(0x11)

        time.sleep_ms(120)

        self.clear()
        self.command(0x29)

        print("LCD initialized: 240x135")

    def window(self, x0, y0, x1, y1):

        x0 += 40
        x1 += 40
        y0 += 53
        y1 += 53

        self.command(
            0x2A,
            bytes((
                x0 >> 8, x0 & 255,
                x1 >> 8, x1 & 255
            ))
        )

        self.command(
            0x2B,
            bytes((
                y0 >> 8, y0 & 255,
                y1 >> 8, y1 & 255
            ))
        )

    def clear(self):

        for i in range(len(self.row)):
            self.row[i] = 0

        self.window(
            0, 0,
            LCD_WIDTH - 1,
            LCD_HEIGHT - 1
        )

        self.command(0x2C)

        self.cs(0)
        self.dc(1)

        try:
            for _ in range(LCD_HEIGHT):
                self.spi.write(self.row)
        finally:
            self.cs(1)

    def show(
        self,
        frame,
        flip_y=True,
        mode="crop"
    ):
        """
        Draw frame row by row.

        This intentionally uses a separate LCD
        address window for each row, restoring
        the display method that worked for
        individual photographs.
        """

        if len(frame) != FRAME_BYTES:
            raise ValueError(
                "Invalid camera frame size"
            )

        if mode == "crop":

            src_x = 2
            src_y = 72
            src_w = 320
            src_h = 180

            dst_x = 0
            dst_w = 240

        elif mode == "fit":

            src_x = 0
            src_y = 0
            src_w = 324
            src_h = 324

            dst_x = 52
            dst_w = 135

        elif mode == "stretch":

            src_x = 0
            src_y = 0
            src_w = 324
            src_h = 324

            dst_x = 0
            dst_w = 240

        else:
            raise ValueError(
                "Invalid display mode"
            )

        if self._view_mode != mode:

            self._view_x = tuple(
                src_x + x * src_w // dst_w
                for x in range(dst_w)
            )

            self.clear()
            self._view_mode = mode

        row = self.row
        lookup = self.gray
        x_map = self._view_x

        row_view = memoryview(row)[:dst_w * 2]

        for y in range(LCD_HEIGHT):

            relative_y = (
                y * src_h // LCD_HEIGHT
            )

            if flip_y:
                source_y = (
                    src_y + src_h - 1 - relative_y
                )
            else:
                source_y = src_y + relative_y

            source_start = source_y * WIDTH

            for x in range(dst_w):

                pixel = frame[
                    source_start + x_map[x]
                ]

                color_index = pixel * 2
                output_index = x * 2

                row[output_index] = (
                    lookup[color_index]
                )

                row[output_index + 1] = (
                    lookup[color_index + 1]
                )

            self.window(
                dst_x,
                y,
                dst_x + dst_w - 1,
                y
            )

            self.command(
                0x2C,
                row_view
            )

    def test_screen(self):
        """
        Change the LCD between solid colors.
        Does not use the camera.
        """

        colors = (
            (0xF8, 0x00),  # Red
            (0x07, 0xE0),  # Green
            (0x00, 0x1F),  # Blue
            (0xFF, 0xFF),  # White
            (0x00, 0x00),  # Black
        )

        for high, low in colors:

            for x in range(0, len(self.row), 2):
                self.row[x] = high
                self.row[x + 1] = low

            self.window(
                0, 0,
                LCD_WIDTH - 1,
                LCD_HEIGHT - 1
            )

            self.command(0x2C)

            self.cs(0)
            self.dc(1)

            try:
                for _ in range(LCD_HEIGHT):
                    self.spi.write(self.row)
            finally:
                self.cs(1)

            time.sleep_ms(500)

        self._view_mode = None

    def close(self):

        self.cs(1)
        self.spi.deinit()

