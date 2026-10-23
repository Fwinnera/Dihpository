#!/usr/bin/env python3
"""Build candidate C on a disengage base: do not walk back into a lost fight.

The disengage rule leaves a fight once our side's power within five tiles falls
below DISENGAGE_RATIO of the enemy's, and hands control back the moment no enemy
is within five tiles. The objective was cleared on the way out, so the next
`choose_group` picks again -- with only the enemies it can still see, which after
a successful exit is usually none. Nothing stops it choosing the camp it just
fled, and the existing proximity term is at most +20 on a score in the hundreds.

This adds a short memory of enemy sightings and refuses any camp where the
disengage rule would fire on arrival: enemy power that could have reached the
camp since it was seen (a tile a round) against ours plus allies already there,
on the same health-times-strength measure and the same ratio. No new threshold
is tuned; only how long a sighting is kept.

    mkavoid.py gs_dis075_avoid                     # on gs_dis075
    mkavoid.py gs_vv_dis075_avoid --base gs_vv_dis075
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"

CONFIG = '''
# Keep an enemy sighting this many rounds when choosing camps. Disengaging loses
# sight of the enemy within a turn or two; without it the next camp choice walks
# straight back into the fight it just left.
SIGHTING_MEMORY = {memory}
'''

REMEMBER = '''    def remember(self, seen, enemies):
        """Enemy champions sighted in the last SIGHTING_MEMORY rounds, by handle."""
        now = bc.round_number()
        for enemy in enemies:
            turn.check()
            p = enemy.position()
            self.sightings[enemy.__index__()] = (
                p.x, p.y, enemy.health() * max(1, enemy.strength()), now)
        if len(seen) != len(enemies):
            for enemy in seen:
                if enemy not in enemies:
                    self.sightings.pop(enemy.__index__(), None)
        for handle in [h for h, s in self.sightings.items()
                       if now - s[3] > config.SIGHTING_MEMORY]:
            del self.sightings[handle]

'''

CONTEXT = '''

def threat_context(me, team, sightings):
    """Remembered enemies as (x, y, power, reach), and visible allies' power.

    Reach is the disengage radius plus a tile for every round since the sighting.
    Returns None when nothing has been seen recently, which is the common case.
    """
    if not sightings:
        return None
    now = bc.round_number()
    threats = [(x, y, power, config.DISENGAGE_RADIUS + now - seen)
               for x, y, power, seen in sightings.values()]
    allies = []
    for ally in team.allies:
        turn.check()
        if ally != me and ally.is_alive() and ally.is_visible():
            q = ally.position()
            allies.append((q.x, q.y, ally.health() * max(1, ally.strength()) * 0.75))
    return threats, allies, me.health() * max(1, me.strength())


def contested(coords, context):
    """Would the disengage rule fire on arrival at any of these tiles?"""
    threats, allies, friendly = context
    hostile = 0.0
    for tx, ty, power, reach in threats:
        for px, py in coords:
            if max(abs(px - tx), abs(py - ty)) <= reach:
                hostile += power
                break
    if not hostile:
        return False
    for ax, ay, power in allies:
        for px, py in coords:
            if max(abs(px - ax), abs(py - ay)) <= config.DISENGAGE_RADIUS:
                friendly += power
                break
    return friendly < hostile * config.DISENGAGE_RATIO
'''

# (file, old, new): each old string must occur exactly once in the base.
EDITS = [
    ("bot.py",
     "        self.disengaging = False\n",
     "        self.disengaging = False\n        self.sightings = {}\n"),
    ("bot.py",
     "    def play_turn(self):\n",
     REMEMBER + "    def play_turn(self):\n"),
    ("bot.py",
     "        enemies = [e for e in bc.vision.champions(bc.Team.ENEMY) if e.is_alive()]\n",
     "        seen = bc.vision.champions(bc.Team.ENEMY)\n"
     "        enemies = [e for e in seen if e.is_alive()]\n"
     "        self.remember(seen, enemies)\n"),
    ("bot.py",
     "                                              self.current_group, self.team, enemies)\n",
     "                                              self.current_group, self.team, enemies,\n"
     "                                              self.sightings)\n"),
    ("bot.py",
     "            objective = strategy.choose_cooperative(self.metadata, me, self.respawns, self.team)\n",
     "            objective = strategy.choose_cooperative(self.metadata, me, self.respawns, self.team,\n"
     "                                                    self.sightings)\n"),
    ("strategy.py",
     "def choose_group(metadata, me, respawns, current, team, enemies):\n",
     "def choose_group(metadata, me, respawns, current, team, enemies, sightings=None):\n"),
    ("strategy.py",
     "    best, best_score = None, float('inf')\n",
     "    context = threat_context(me, team, sightings)\n"
     "    best, best_score = None, float('inf')\n"),
    ("strategy.py",
     "        positions = [p for p in objective.positions if reached.is_set(p)]\n"
     "        if not positions:\n"
     "            continue\n"
     "        travel = min(field.get(p) for p in positions)\n"
     "        reward = False\n",
     "        positions = [p for p in objective.positions if reached.is_set(p)]\n"
     "        if not positions:\n"
     "            continue\n"
     "        if context is not None and contested(objective.coords, context):\n"
     "            continue\n"
     "        travel = min(field.get(p) for p in positions)\n"
     "        reward = False\n"),
    ("strategy.py",
     "def choose_cooperative(metadata, me, respawns, team):\n",
     "def choose_cooperative(metadata, me, respawns, team, sightings=None):\n"),
    ("strategy.py",
     "    best, score = None, float('inf')\n",
     "    context = threat_context(me, team, sightings)\n"
     "    best, score = None, float('inf')\n"),
    ("strategy.py",
     "        positions = [p for p in o.positions if reached.is_set(p)]\n"
     "        if not positions:\n"
     "            continue\n"
     "        hp = o.hp\n",
     "        positions = [p for p in o.positions if reached.is_set(p)]\n"
     "        if not positions:\n"
     "            continue\n"
     "        if context is not None and contested(o.coords, context):\n"
     "            continue\n"
     "        hp = o.hp\n"),
]


def build(name: str, base: str, memory: int) -> None:
    src_base = WS / "bots" / base / "src"
    if "DISENGAGE_RATIO" not in (src_base / "config.py").read_text():
        sys.exit(f"{base} has no disengage rule; build it with mkdisengage.py first")
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WS / "bots" / base, dst)
    src = dst / "src"

    texts = {f: (src / f).read_text() for f in ("bot.py", "strategy.py", "config.py")}
    for f, old, new in EDITS:
        if texts[f].count(old) != 1:
            sys.exit(f"{f}: anchor occurs {texts[f].count(old)} times, not once: {old!r}")
        texts[f] = texts[f].replace(old, new, 1)
    texts["strategy.py"] = texts["strategy.py"].rstrip("\n") + "\n" + CONTEXT
    anchor = "DISENGAGE_RADIUS = 5\n"
    if texts["config.py"].count(anchor) != 1:
        sys.exit("config anchor missing")
    texts["config.py"] = texts["config.py"].replace(
        anchor, anchor + CONFIG.format(memory=memory), 1)
    for f, t in texts.items():
        (src / f).write_text(t)

    main = src / "main.py"
    text = re.sub(r'\n    print\("BOTTAG [^"]+", flush=True\)\n', "", main.read_text())
    main.write_text(text.replace(
        "def main():", f'def main():\n    print("BOTTAG {name}", flush=True)\n', 1))
    for p in src.glob("*.py"):
        ast.parse(p.read_text())
    print(f"  {name}: from {base}, memory {memory}, parses, tagged")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--base", default="gs_dis075")
    ap.add_argument("--memory", type=int, default=8)
    a = ap.parse_args()
    build(a.name, a.base, a.memory)
