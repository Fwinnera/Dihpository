"""Discard stale plans if the runner suspends us at a fuel boundary."""
import cambc as bc

started = -1
walked = False
MIN_FUEL = 1_000  # SDK examples use this guard; the getter is runner-dependent.


class Replan(Exception):
    pass


def begin():
    global started, walked
    started = bc.round_number()
    walked = False


def check():
    current = bc.round_number()
    fuel = bc.fuel_remaining()
    if current != started or fuel < MIN_FUEL:
        raise Replan()


def may_cast(ability):
    # RULE: an ability marked exclusive_with_movement cannot follow a normal walk.
    # WHY: skip only the illegal spell and preserve a legal basic attack this turn.
    info = ability.info()
    return info is not None and not (walked and info.exclusive_with_movement)
