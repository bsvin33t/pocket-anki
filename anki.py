# AnkiConnect client and the offline card cache in microcontroller.nvm.
import json
import os
import random

import microcontroller
import socketpool
import wifi

from text import back_side, parse_env, strip_html

HOST = os.getenv("ANKI_HOST")
PORT = int(os.getenv("ANKI_PORT") or 8766)
KEY = os.getenv("ANKI_KEY") or None
DECKS = [d.strip() for d in (os.getenv("ANKI_DECK") or "").split(",") if d.strip()]  # comma-separated
QUERY = "(%s) " % (" OR ".join('"deck:%s"' % d for d in DECKS) or "deck:current")

try:
    with open("/.env") as f:  # Wi-Fi secrets live in .env, not settings.toml
        ENV = parse_env(f.read())
except OSError:
    ENV = {}

pool = socketpool.SocketPool(wifi.radio)


def call(action, **params):
    """One AnkiConnect request. HTTP/1.0, so the server closes the connection after its reply."""
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
    finally:
        s.close()
    head, _, reply = buf.partition(b"\r\n\r\n")
    status = head.split(b"\r\n")[0]
    if b" 200 " not in status:  # for example another web server on this port
        raise RuntimeError("Anki on %s:%d: %s" % (HOST, PORT, status.decode() or "no reply"))
    r = json.loads(reply)
    if r["error"]:
        raise RuntimeError(r["error"])
    return r["result"]


# Cache layout in NVM: 2-byte length + JSON {"c": [[cardId, front, back], ...], "g": [[cardId, ease], ...]}
# (8 KB; the CIRCUITPY drive is read-only to code while the Mac mounts it)
NVM = microcontroller.nvm
LIMIT = len(NVM) - 2
MAX_TEXT = 300  # characters per card side; the screen shows about 160 anyway


def load():
    n = NVM[0] << 8 | NVM[1]
    try:
        if 0 < n <= LIMIT:
            return json.loads(bytes(NVM[2 : 2 + n]))
    except ValueError:
        pass
    return {"c": [], "g": []}


def save(state):
    b = json.dumps(state).encode()
    NVM[0 : 2 + len(b)] = bytes([len(b) >> 8, len(b) & 255]) + b


def send_grades(state):
    """Send saved grades to Anki. The caller saves the state afterwards."""
    if state["g"]:
        call("answerCards", answers=[{"cardId": i, "ease": e} for i, e in state["g"]])
        state["g"] = []


def fetch_cards(ids):
    """Yield [cardId, front, back] in plain text, 20 cards per request, only as far as the caller reads."""
    for i in range(0, len(ids), 20):
        for c in call("cardsInfo", cards=ids[i : i + 20]):
            yield [c["cardId"], strip_html(c["question"])[:MAX_TEXT], strip_html(back_side(c["answer"]))[:MAX_TEXT]]


def sync(state):
    """Send saved grades, then refill the cache with as many cards as fit: due reviews (mixed), then new. Raises when offline."""
    if not wifi.radio.connected:
        wifi.radio.connect(ENV.get("WIFI_SSID"), ENV.get("WIFI_PASSWORD"))
    send_grades(state)
    save(state)  # before the refill can fail: grades still in NVM would be sent twice
    due = call("findCards", query=QUERY + "is:due")
    due.sort(key=lambda _: random.random())  # mix reviews from all decks
    ids = due + call("findCards", query=QUERY + "is:new")
    cards, size = [], len(json.dumps({"c": [], "g": []}))
    for card in fetch_cards(ids):
        size += len(json.dumps(card)) + 2  # ", " between list items
        if size > LIMIT:
            break
        cards.append(card)
    state["c"] = cards
    save(state)
