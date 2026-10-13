# Anki flashcards on the SpotPear ESP32-S3 1.54 "muma", talking to AnkiConnect.
# Button (BOOT): tap = show answer / Good, hold 2 s = Again (next card shows at once), hold 6 s = off.

# IO3 is the power latch: high keeps the board on when running on battery. Low (or released, as on every
# CircuitPython reload) turns it off, so a file update over USB turns the device off once.
# Set first, before the slower imports: the power button only powers the board until this line runs.
import board
import digitalio

power = digitalio.DigitalInOut(board.IO3)
power.switch_to_output(True)

import json
import os
import random
import time

import array
import audiobusio
import busdisplay
import busio
import displayio
import fourwire
import microcontroller
import socketpool
import synthio
import terminalio
import wifi

from text import back_side, center, strip_html, wrap

backlight = digitalio.DigitalInOut(board.IO42)
backlight.switch_to_output(False)  # inverted: low = on

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


# Characters that the built-in font lacks; anything else missing shows as "?".
FALLBACK = {"Ö": "Oe", "’": "'", "‘": "'", "“": '"', "”": '"', "„": '"', "–": "-", "—": "-", "…": "..."}


def show(text, footer=""):
    text = "".join(c if c < "\x80" or terminalio.FONT.get_glyph(ord(c)) else FALLBACK.get(c, "?") for c in text)
    lines = wrap(text, COLS)
    body = ROWS - 2 if footer else ROWS
    if len(lines) > body:  # ponytail: long cards are cut, add paging if that bites
        lines = lines[: body - 1] + [lines[body - 1][: COLS - 3] + "..."]
    term.write("\x1b[2J\x1b[H" + "\r\n".join(center(lines, COLS, body)))
    if footer:
        term.write("\x1b[%d;1H%s" % (ROWS, center([footer[:COLS]], COLS, 1)[0]))


button = digitalio.DigitalInOut(board.IO0)  # BOOT button
button.switch_to_input(digitalio.Pull.UP)


def power_off():
    show("Turning off...\n\nTo turn on: press the\nother button.")
    save()
    time.sleep(2)
    backlight.value = True
    power.value = False  # releases the power latch, same as the vendor firmware
    time.sleep(10)


held_since, used = None, False  # one hold can span screens: Again at 2 s, then power off at 6 s


def press(again=False):
    """Return False on a tap (on release). With again=True, return True as soon as the button is held 2 s.
    A hold that already returned True is ignored on release. A 6-second hold turns the device off."""
    global held_since, used
    while True:
        time.sleep(0.01)
        if not button.value:  # pressed (active low)
            if held_since is None:
                held_since, used = time.monotonic(), False
            held = time.monotonic() - held_since
            if held > 6:
                power_off()
            if again and not used and held > 2:
                used = True
                return True
        elif held_since is not None:  # released
            held_since = None
            if not used:
                return False


# Wi-Fi secrets live in .env (KEY=value lines), not settings.toml
ENV = {}
try:
    with open("/.env") as f:
        for line in f:
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                ENV[k.strip()] = v.strip().strip("\"'")
except OSError:
    pass

HOST = os.getenv("ANKI_HOST")
PORT = int(os.getenv("ANKI_PORT") or 8765)
KEY = os.getenv("ANKI_KEY") or None
DECKS = [d.strip() for d in (os.getenv("ANKI_DECK") or "").split(",") if d.strip()]  # comma-separated
QUERY = "(%s) " % (" OR ".join('"deck:%s"' % d for d in DECKS) or "deck:current")
pool = socketpool.SocketPool(wifi.radio)


def anki(action, **params):
    body = json.dumps({"action": action, "version": 6, "key": KEY, "params": params}).encode()
    s = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    s.settimeout(8)
    try:
        s.connect((HOST, PORT))
        msg = ("POST / HTTP/1.0\r\nHost: %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % (HOST, len(body))).encode() + body
        while msg:
            msg = msg[s.send(msg):]
        buf, chunk = b"", bytearray(2048)
        while True:
            n = s.recv_into(chunk)
            if not n:
                break
            buf += chunk[:n]
            head, sep, rest = buf.partition(b"\r\n\r\n")
            if sep:  # stop once Content-Length bytes arrived, in case the server keeps the socket open
                cl = [l for l in head.lower().split(b"\r\n") if l.startswith(b"content-length:")]
                if cl and len(rest) >= int(cl[0].split(b":")[1]):
                    break
    finally:
        s.close()
    reply = buf.partition(b"\r\n\r\n")[2]
    if not reply:
        raise RuntimeError("No reply from Anki on port %d" % PORT)
    r = json.loads(reply)
    if r["error"]:
        raise RuntimeError(r["error"])
    return r["result"]


# Offline cache in microcontroller.nvm (8 KB; the CIRCUITPY drive is read-only to code while the Mac mounts it).
# Layout: 2-byte length + JSON {"c": [[cardId, front, back], ...], "g": [[cardId, ease], ...]}
NVM = microcontroller.nvm


def load():
    n = NVM[0] << 8 | NVM[1]
    try:
        if 0 < n <= len(NVM) - 2:
            return json.loads(bytes(NVM[2 : 2 + n]))
    except ValueError:
        pass
    return {"c": [], "g": []}


def save():
    b = json.dumps(state).encode()
    NVM[0 : 2 + len(b)] = bytes([len(b) >> 8, len(b) & 255]) + b


def send_grades():
    if state["g"]:
        anki("answerCards", answers=[{"cardId": i, "ease": e} for i, e in state["g"]])
        state["g"] = []


def sync():
    """Send saved grades, then refill the cache with as many due cards as fit. Raises when offline."""
    if not wifi.radio.connected:
        wifi.radio.connect(ENV.get("WIFI_SSID"), ENV.get("WIFI_PASSWORD"))
    send_grades()
    due = anki("findCards", query=QUERY + "is:due")
    for i in range(len(due) - 1, 0, -1):  # shuffle so reviews from all decks mix (CircuitPython has no random.shuffle)
        j = random.randrange(i + 1)
        due[i], due[j] = due[j], due[i]
    ids = due + anki("findCards", query=QUERY + "is:new")  # reviews before new cards
    cards, size = [], 20  # 20 bytes for the JSON wrapper
    for i in range(0, len(ids), 20):
        if size > len(NVM) - 2:
            break
        for c in anki("cardsInfo", cards=ids[i : i + 20]):
            card = [c["cardId"], strip_html(c["question"])[:300], strip_html(back_side(c["answer"]))[:300]]
            size += len(json.dumps(card)) + 2
            if size <= len(NVM) - 2:
                cards.append(card)
    state["c"] = cards
    save()


state = load()
chime()
while True:
    show("Syncing...", "%d grades to send" % len(state["g"]) if state["g"] else "")
    try:
        sync()
        online = True
    except Exception as e:  # no Wi-Fi, Anki closed: study from the cache
        online, error = False, e
    if not state["c"]:
        show("No cards due.\n\nGreat work!" if online else "Offline, no saved cards.\n\n%s" % error, "tap: sync again")
        press()
        continue
    while state["c"]:
        cid, front, back = state["c"][0]
        show(front, "%d %s tap: show" % (len(state["c"]), "left" if online else "offline"))
        press()
        show(back, "tap:Good hold:Again")
        state["g"].append([cid, 1 if press(again=True) else 3])
        state["c"].pop(0)
        if online:
            try:
                send_grades()
                continue  # nothing to save: the next sync replaces the cache anyway
            except Exception:
                online = False
        save()  # ponytail: one NVM write per offline grade; batch writes if flash wear ever matters
