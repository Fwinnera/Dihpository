"""Six ten-bit task reservations: nine group bits and one support-role bit.

Zero means idle; the low nine bits hold group index + 1 (up to 510).
Official maps have at most 46 groups. Only collectors reserve the reward;
supporters reserve their assistance, not a second claim on the same pickup.
"""
import cambc as bc
import turn

class Teamwork:
    def __init__(self):
        self.allies = bc.champions(bc.Team.ALLY)
        self.slot = self.allies.index(bc.me())
        self.buffer = bytearray(8)

    def assignments(self):
        bc.shared_memory.read(0, self.buffer)
        word = int.from_bytes(self.buffer, 'little')
        return [(word >> (10*i) & 511) - 1 for i in range(len(self.allies))]

    def claim(self, group=None, support=False):
        value = 0 if group is None else group.__index__() + 1
        if not 0 <= value <= 511:
            raise ValueError('camp index exceeds reservation capacity')
        if value and support:
            value |= 512
        turn.check()
        bc.shared_memory.read(0, self.buffer)
        word = int.from_bytes(self.buffer, 'little')
        shift = self.slot * 10
        word = (word & ~(1023 << shift)) | (value << shift)
        turn.check()
        bc.shared_memory.write(0, word.to_bytes(8, 'little'))

    def collector(self, handle, region=None):
        turn.check()
        bc.shared_memory.read(0, self.buffer)
        word = int.from_bytes(self.buffer, 'little')
        candidates = []
        for i, ally in enumerate(self.allies):
            turn.check()
            value = word >> (10*i) & 1023
            if not value & 512 and (value & 511) == handle + 1 and ally.is_alive():
                candidates.append(i)
        if region is not None:
            # A task already being executed is not stolen by a traveller.
            for i in candidates:
                ally = self.allies[i]
                if ally.is_visible():
                    position = ally.position()
                    turn.check()
                    if region.is_set(position):
                        return i
        return candidates[0] if candidates else None
