# SpotPear ESP32-S3 1.54" "muma" board: power latch, screen, speaker, BOOT button.
# Import this first: the power button only powers the board until the IO3 line below runs.

# IO3 is the power latch: high keeps the board on when running on battery. Low (or released, as on every
# CircuitPython reload) turns it off, so a file update over USB turns the device off once.
import board
import digitalio

power = digitalio.DigitalInOut(board.IO3)
power.switch_to_output(True)

import array
import time

import audiobusio
import busdisplay
import busio
import displayio
import fourwire
import synthio
import terminalio

from text import center, to_font, wrap

backlight = digitalio.DigitalInOut(board.IO42)
backlight.switch_to_output(False)  # inverted: low = on

boot_button = digitalio.DigitalInOut(board.IO0)
boot_button.switch_to_input(digitalio.Pull.UP)


def boot_down():
    return not boot_button.value  # active low


def off():
    """Release the power latch, same as the vendor firmware. Returns only if something else keeps the board powered."""
    backlight.value = True
    power.value = False
    time.sleep(10)


# ST7789 240x240 panel
displayio.release_displays()
spi = busio.SPI(clock=board.IO4, MOSI=board.IO2)
bus = fourwire.FourWire(spi, command=board.IO47, chip_select=board.IO5, reset=board.IO38, baudrate=40_000_000)
INIT = (
    b"\x01\x80\x96"  # software reset, 150 ms
    b"\x11\x80\xff"  # sleep out, 255 ms
    b"\x3a\x81\x55\x0a"  # 16-bit color, 10 ms
    b"\x36\x01\x00"  # memory access order
    b"\xbb\x01\x38"  # VCOM, value from the vendor firmware
    b"\x21\x80\x0a"  # inversion on (this panel needs it)
    b"\x13\x80\x0a"  # normal mode
    b"\x29\x80\xff"  # display on
)
display = busdisplay.BusDisplay(bus, INIT, width=240, height=240)

SCALE = 2  # terminalio font is 6x12: 40x20 characters at scale 1, 20x10 at scale 2
FW, FH = terminalio.FONT.get_bounding_box()
COLS, ROWS = 240 // (FW * SCALE), 240 // (FH * SCALE)
palette = displayio.Palette(2)
palette[0], palette[1] = 0x000000, 0xFFFFFF
grid = displayio.TileGrid(terminalio.FONT.bitmap, pixel_shader=palette, width=COLS, height=ROWS, tile_width=FW, tile_height=FH)
root = displayio.Group(scale=SCALE)
root.append(grid)
display.root_group = root
term = terminalio.Terminal(grid, terminalio.FONT)


def show(text, footer=""):
    """Text centered on screen, with an optional footer on the last row."""
    lines = wrap(to_font(text, lambda c: terminalio.FONT.get_glyph(ord(c))), COLS)
    body = ROWS - 2 if footer else ROWS
    if len(lines) > body:  # ponytail: long cards are cut, add paging if that bites
        lines = lines[: body - 1] + [lines[body - 1][: COLS - 3] + "..."]
    term.write("\x1b[2J\x1b[H" + "\r\n".join(center(lines, COLS, body)))
    if footer:
        term.write("\x1b[%d;1H%s" % (ROWS, center([footer[:COLS]], COLS, 1)[0]))


def chime():
    """Play C-E-G (C5, E5, G5) as square waves through the ES8311 codec."""
    pa = digitalio.DigitalInOut(board.IO46)  # speaker amplifier
    pa.switch_to_output(True)
    i2c = busio.I2C(board.IO14, board.IO15)
    while not i2c.try_lock():
        pass
    # ES8311 setup for 16-bit I2S playback, clocked from BCLK x8 (no MCLK); register values from Espressif's es8311 driver
    for reg, val in ((0x00, 0x1F), (0x45, 0x00), (0x01, 0xBF), (0x02, 0x18), (0x03, 0x10), (0x04, 0x10), (0x05, 0x00),
                     (0x09, 0x0C), (0x0A, 0x0C), (0x0B, 0x00), (0x0C, 0x00), (0x10, 0x1F), (0x11, 0x7F), (0x00, 0x80),
                     (0x0D, 0x01), (0x0E, 0x02), (0x12, 0x00), (0x13, 0x10), (0x1C, 0x6A), (0x37, 0x08),
                     (0x32, 0xB0),  # DAC volume: 0xBF = 0 dB
                     (0x31, 0x00)):
        i2c.writeto(0x18, bytes([reg, val]))
    i2c.unlock()
    i2s = audiobusio.I2SOut(bit_clock=board.IO9, word_select=board.IO45, data=board.IO8)
    square = array.array("h", [9000] * 16 + [-9000] * 16)
    synth = synthio.Synthesizer(sample_rate=22050, waveform=square,
                                envelope=synthio.Envelope(attack_time=0.005, release_time=0.08, sustain_level=0.8))
    i2s.play(synth)
    for note in (72, 76, 79):
        synth.press(note)
        time.sleep(0.12)
        synth.release(note)
        time.sleep(0.03)
    time.sleep(0.3)
    for part in (i2s, synth, i2c, pa):  # free the pins; amplifier off avoids hiss
        part.deinit()
