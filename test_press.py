# Run on the Mac: python3 test_press.py
from button import Button, PowerOff


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, d):
        self.now += d
        if self.now > 60:
            raise TimeoutError("press() never returned")


def run(holds, calls):
    """holds: (start, end) seconds when BOOT is down. calls: the again= argument of each press() call."""
    clock = Clock()
    button = Button(lambda: any(a <= clock.now < b for a, b in holds), clock)
    out = []
    try:
        for again in calls:
            out.append((button.press(again=again), round(clock.now, 1)))
    except PowerOff:
        out.append(("off", round(clock.now, 1)))
    return out


assert run([(1, 1.3)], [True]) == [(False, 1.3)]  # tap on the answer: Good, on release
assert run([(1, 4)], [True])[0] == (True, 3.0)  # hold: Again at 2 s, while still held
assert run([(1, 4), (5, 5.2)], [True, False]) == [(True, 3.0), (False, 5.2)]  # release of that hold is not a tap
assert run([(1, 9)], [True, False]) == [(True, 3.0), ("off", 7.0)]  # keep holding: off at 6 s from the start
assert run([(1, 2.5)], [False]) == [(False, 2.5)]  # front side: a 1.5 s hold is just a tap
assert run([(1, 8)], [False]) == [("off", 7.0)]  # front side: 6 s hold turns off
print("ok")
