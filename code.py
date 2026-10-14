# Anki flashcards on the SpotPear ESP32-S3 1.54" "muma", talking to AnkiConnect, with an offline cache.
# BOOT button: tap = show answer / Good, hold 2 s = Again (next card shows at once), hold 6 s = off.
import hw  # first: it holds the power latch

import time

import anki
from button import Button, PowerOff

button = Button(hw.boot_down)
state = anki.load()
hw.chime()
try:
    while True:
        hw.show("Syncing...", "%d grades to send" % len(state["g"]) if state["g"] else "")
        try:
            anki.sync(state)
            online = True
        except Exception as e:  # no Wi-Fi, Anki closed: study from the cache
            online, error = False, e
        if not state["c"]:
            hw.show("No cards due.\n\nGreat work!" if online else "Offline, no saved cards.\n\n%s" % error, "tap: sync again")
            button.press()
            continue
        while state["c"]:
            cid, front, back = state["c"][0]
            hw.show(front, "%d %s tap: show" % (len(state["c"]), "left" if online else "offline"))
            button.press()
            hw.show(back, "tap:Good hold:Again")
            state["g"].append([cid, 1 if button.press(again=True) else 3])
            state["c"].pop(0)
            if online:
                try:
                    anki.send_grades(state)
                except Exception:
                    online = False
            anki.save(state)  # ponytail: one NVM write per grade; batch writes if flash wear ever matters
except PowerOff:
    hw.show("Turning off...\n\nTo turn on: press the\nother button.")
    anki.save(state)
    time.sleep(2)
    hw.off()
