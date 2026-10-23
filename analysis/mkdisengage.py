#!/usr/bin/env python3
"""Build candidate A (disengage from lost fights) and its calibration logger.

Both come from pristine greatsage and share one function, `combat.local_power`,
so the threshold is calibrated against exactly the number the rule acts on.

    mkdisengage.py gs_fightlog --log           # never disengages, logs the ratio
    mkdisengage.py gs_disengage --ratio 0.8    # the candidate
"""
from __future__ import annotations

import argparse
import ast
import shutil
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"

LOCAL_POWER = '''

def local_power(enemies, allies, radius):
    """Our strength against the enemy champions within `radius` of this champion.

    The health-times-strength measure `choose_enemy` uses, centred on us rather
    than on one target, so it answers whether to be here at all. Returns the
    ratio and the number of enemies counted; the ratio is infinite when none are.
    """
    me = bc.me()
    position = me.position()
    hostile, threats = 0.0, 0
    for enemy in enemies:
        turn.check()
        if enemy.is_visible() and distance(position, enemy.position()) <= radius:
            hostile += enemy.health() * max(1, enemy.strength())
            threats += 1
    if not threats:
        return float('inf'), 0
    allied = me.health() * max(1, me.strength())
    for ally in allies:
        if (ally != me and ally.is_alive() and ally.is_visible()
                and distance(position, ally.position()) <= radius):
            allied += ally.health() * max(1, ally.strength()) * 0.75
    return allied / max(1.0, hostile), threats


def finishing_blow(enemies):
    """An enemy in reach that one attack or cast kills, worth 199 gold to take."""
    me = bc.me()
    attack_mask = me.attack_tiles()
    burst = me.strength() * 2
    best = None
    for enemy in enemies:
        if attack_mask.is_set(enemy.position()):
            kill = burst
            for a in me.abilities():
                if a.is_ready() and (a.is_damage() or a.is_cc() or a.is_aoe_damage()):
                    kill = max(kill, me.strength() + a.damage_amount(enemy))
            if enemy.health() <= kill and (best is None or enemy.health() < best.health()):
                best = enemy
    return best
'''

CONFIG = '''
# Leave a fight when our side's health-times-strength within DISENGAGE_RADIUS
# falls below DISENGAGE_RATIO of theirs, and stay out until it recovers past the
# ratio plus DISENGAGE_HYSTERESIS. Rebuilding all 15,225 ladder kills found 14.6
# fights a game at 8% odds or worse, because retreat counted health and camps
# only: a champion stayed in a lost fight until 30% health and, at move speed 1
# like everyone else, could not get out from there.
DISENGAGE_RATIO = {ratio}
DISENGAGE_HYSTERESIS = 0.2
DISENGAGE_RADIUS = 5
'''

HOOK_ANCHOR = "        holding = self.by_tile.get(me.position())\n"
HOOK = '''        ratio, threats = combat.local_power(enemies, self.team.allies, config.DISENGAGE_RADIUS)
{log}        leave = config.DISENGAGE_RATIO + (config.DISENGAGE_HYSTERESIS if self.disengaging else 0)
        self.disengaging = not at_spawn and threats > 0 and ratio < leave
        if self.disengaging:
            self.status('disengage')
            self.objective = None
            self.team.claim()
            # Take a kill that is already in reach before leaving: it removes a
            # threat and pays 199 gold. Then withdraw on the same turn.
            target = combat.finishing_blow(enemies)
            if target is not None:
                combat.fight(target, enemies)
            nav.retreat(enemies, camps)
            return
'''
LOG = ('        if threats:\n'
       '            print("PW %d %s %.3f %d %.2f %d" % (bc.round_number(), me.champion_name(), '
       'ratio, threats, me.health() / max(1, me.max_health()), me.gem_count()), flush=True)\n')


def build(name: str, ratio: float, log: bool) -> None:
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WS / "bots/greatsage", dst)
    src = dst / "src"

    combat = src / "combat.py"
    combat.write_text(combat.read_text().rstrip("\n") + "\n" + LOCAL_POWER)

    cfg = src / "config.py"
    t = cfg.read_text()
    anchor = "SHOP_INTERVAL = 70\n"
    if anchor not in t:
        sys.exit("config anchor missing")
    cfg.write_text(t.replace(anchor, anchor + CONFIG.format(ratio=ratio), 1))

    bot = src / "bot.py"
    t = bot.read_text()
    for anchor in (HOOK_ANCHOR, "        self.banking = False\n"):
        if t.count(anchor) < 1:
            sys.exit(f"bot anchor missing: {anchor!r}")
    if t.count(HOOK_ANCHOR) != 1:
        sys.exit("hook anchor is not unique")
    t = t.replace(HOOK_ANCHOR, HOOK.format(log=LOG if log else "") + HOOK_ANCHOR, 1)
    t = t.replace("        self.banking = False\n",
                  "        self.banking = False\n        self.disengaging = False\n", 1)
    bot.write_text(t)

    main = src / "main.py"
    main.write_text(main.read_text().replace(
        "def main():", f'def main():\n    print("BOTTAG {name}", flush=True)\n', 1))
    for p in src.glob("*.py"):
        ast.parse(p.read_text())
    print(f"  {name}: ratio {ratio}, log {log}, parses, tagged")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--ratio", type=float, default=0.0)
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()
    build(a.name, a.ratio, a.log)
