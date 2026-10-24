"""Never commit an action from a plan that crossed a fuel suspension."""
import cambc as bc
started = -1
walked = False
MIN_FUEL = 250_000

class Replan(Exception):
    pass

def begin():
    global started, walked
    started = bc.round_number()
    walked = False

def check():
    if bc.round_number() != started or bc.fuel_remaining() < MIN_FUEL:
        raise Replan()

def may_cast(ability):
    info = ability.info()
    return info is not None and not (walked and info.exclusive_with_movement)
