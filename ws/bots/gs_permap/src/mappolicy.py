"""Per-map behaviour, keyed on a signature readable at round zero.

Why per-map at all
------------------
Every global change measured this session helped some maps and hurt others:
champion pressure was +246 on 00swirl and -40 on 00stampede; the efficiency draft
order was +/- across the pool. Those splits were read as noise until the ladder
band was measured -- running the same bot twice on identical pairings reproduces
14 of 15 games byte-identically, so a 9.2-gem band over 15 games. The per-map
differences are therefore real, and a single global constant is one answer forced
onto forty different problems.

The signature
-------------
Width, height and camp-group count identify all 40 maps in the pool with no
collisions (checked against every map). Width and height are free; the group count
is one call the bot already makes. `policy.py` already switches controller on
monolith maps, so per-map dispatch is not a new idea here -- only a more
fine-grained one.

Unknown signatures fall through to the defaults, so a new map behaves exactly as
the bot did before this file existed.
"""

CHAMPION_PRESSURE = "champion_pressure"

# Measured on the ladder, identical pairings, three games per map. Figures are the
# mean gem delta from counting enemy champions in the withdrawal threshold.
_OVERRIDES = {
    # Applied: gains far beyond the 9.2-gem band.
    (45, 30, 22): {CHAMPION_PRESSURE: True},    # 00swirl      +246, was 0-8
    (50, 50, 29): {CHAMPION_PRESSURE: True},    # 01elk_arena  +240, was 0-3
    (31, 31, 15): {CHAMPION_PRESSURE: True},    # 01gold_rush  +187
    (60, 60, 46): {CHAMPION_PRESSURE: True},    # 01islands     +67, was 0-8
    (61, 71, 28): {CHAMPION_PRESSURE: True},    # 01fracture    +58

    # Withheld: the same change measured negative on maps we already win.
    (60, 50, 13): {CHAMPION_PRESSURE: False},   # 00stampede    -40
    (41, 41, 20): {CHAMPION_PRESSURE: False},   # 00collision   -25, 6-0 without it
    (71, 71, 30): {CHAMPION_PRESSURE: False},   # 00corners     -17, 3-0 without it
}

# Everything not listed keeps the behaviour the bot had before: measured neutral
# (01big_world +6, 00eight +4) or not yet measured at all.
_DEFAULTS = {CHAMPION_PRESSURE: False}

_cache = None


def bind(groups):
    """Fix the signature from the group list the bot has already fetched.

    Asking the engine for `camp_groups()` here would cost a call, and the engine
    is deterministic: a few hundred instructions of extra fuel shifts which turns
    exhaust their budget and sends the whole game down a different trajectory.
    That was measured directly -- a loop whose result nothing reads moved 15 of 39
    local maps and swung the gem mean by 22. So the signature is built from data
    the caller already holds, and detection costs nothing at all.
    """
    global _cache
    if _cache is None:
        from cambc import game_map as gm
        _cache = (gm.width(), gm.height(), len(groups))
    return _cache


def get(name):
    """Look up one behaviour flag for the map being played."""
    if _cache is None:
        return _DEFAULTS.get(name)        # bind() not reached yet this turn
    return _OVERRIDES.get(_cache, {}).get(name, _DEFAULTS.get(name))
