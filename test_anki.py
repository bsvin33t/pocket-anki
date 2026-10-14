# Run on the Mac: python3 test_anki.py
# Loads anki.py with fake CircuitPython modules (nvm, Wi-Fi, sockets) and a fake AnkiConnect.
import json
import sys
import types

nvm = bytearray(b"\xff" * 8192)  # erased flash
replies = []  # raw HTTP replies, one per socket


class Socket:
    def settimeout(self, t): pass
    def connect(self, addr): self.reply = replies.pop(0)
    def send(self, b): return len(b)
    def close(self): pass

    def recv_into(self, buf):  # whole reply in one read, then 0 = server closed
        data, self.reply = self.reply, b""
        buf[: len(data)] = data
        return len(data)


sys.modules["microcontroller"] = types.SimpleNamespace(nvm=nvm)
sys.modules["wifi"] = types.SimpleNamespace(radio=types.SimpleNamespace(connected=True))
sys.modules["socketpool"] = types.SimpleNamespace(SocketPool=lambda radio: types.SimpleNamespace(AF_INET=0, SOCK_STREAM=0, socket=lambda *a: Socket()))
import anki  # noqa: E402

# call(): a 501 from another web server on the port gives a readable error, not a JSON error
replies.append(b"HTTP/1.0 501 Unsupported method ('POST')\r\nContent-Type: text/html\r\n\r\n<html>")
try:
    anki.call("version")
    raise AssertionError("expected an error")
except RuntimeError as e:
    assert "501" in str(e), e
replies.append(b"HTTP/1.1 200 OK\r\nContent-Length: 30\r\n\r\n" + b'{"result": 6, "error": null}')
assert anki.call("version") == 6

# empty or erased NVM loads as an empty cache
assert anki.load() == {"c": [], "g": []}

# sync(): grades are persisted as sent before the refill, so a failed refill cannot send them twice
log = []


def fake_call(action, **params):
    log.append(action)
    if action == "findCards":
        raise RuntimeError("Anki closed mid-sync")
    return []


anki.call = fake_call
state = {"c": [[1, "a", "b"]], "g": [[1, 3]]}
anki.save(state)  # an offline grade, saved as the study loop does
assert anki.load()["g"] == [[1, 3]]
try:
    anki.sync(state)
except RuntimeError:
    pass
assert log == ["answerCards", "findCards"]
assert anki.load()["g"] == [], "grades must not stay in NVM after answerCards succeeded"

# sync(): the refill stops at the NVM size, due cards come before new ones, and the saved cache loads back
DUE, NEW = list(range(1, 300)), list(range(1000, 1300))


def deck_call(action, **params):
    if action == "findCards":
        return list(DUE if "is:due" in params["query"] else NEW)
    if action == "cardsInfo":
        return [{"cardId": i, "question": "<b>wort %d</b>" % i, "answer": "x<hr id=answer>meaning %d" % i} for i in params["cards"]]
    return []


anki.call = deck_call
state = {"c": [], "g": []}
anki.sync(state)
saved = nvm[0] << 8 | nvm[1]
assert 0 < saved <= anki.LIMIT
assert anki.load() == state
assert set(c[0] for c in state["c"]) <= set(DUE) and len(state["c"]) > 100  # reviews fill the cache first
assert state["c"][0][1:] == ["wort %d" % state["c"][0][0], "meaning %d" % state["c"][0][0]]
print("ok")
