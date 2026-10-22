"""Recover from an impassable objective without confusing attacks with idling."""


class Progress:
    def __init__(self, limit=12):
        self.limit = limit
        self.reset()

    def reset(self):
        self.signature = None
        self.ticks = 0

    def blocked(self, signature):
        if signature == self.signature:
            self.ticks += 1
        else:
            self.signature, self.ticks = signature, 0
        return self.ticks >= self.limit
