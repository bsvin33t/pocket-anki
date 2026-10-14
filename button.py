# BOOT button gestures: tap, 2-second hold (Again), 6-second hold (power off). No hardware imports here.
import time

AGAIN_AFTER = 2  # seconds
OFF_AFTER = 6


class PowerOff(Exception):
    pass


class Button:
    def __init__(self, is_down, clock=time):
        self.is_down = is_down
        self.clock = clock
        # One hold can span screens: it returns Again at 2 s and keeps counting toward power off at 6 s.
        self.held_since = None
        self.used = False

    def press(self, again=False):
        """Return False on a tap (on release). With again=True, return True as soon as the button is held 2 s.
        A hold that already returned True is ignored on release. Raise PowerOff after a 6-second hold."""
        while True:
            self.clock.sleep(0.01)
            if self.is_down():
                if self.held_since is None:
                    self.held_since, self.used = self.clock.monotonic(), False
                held = self.clock.monotonic() - self.held_since
                if held > OFF_AFTER:
                    raise PowerOff()
                if again and not self.used and held > AGAIN_AFTER:
                    self.used = True
                    return True
            elif self.held_since is not None:  # released
                self.held_since = None
                if not self.used:
                    return False
