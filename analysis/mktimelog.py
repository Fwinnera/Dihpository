#!/usr/bin/env python3
"""Build a time-use logger from any Python bot: where does each champion-turn go?

The top five teams spend 16.5-17.9% of the game hitting camps; we spend 6.5%
(profile_top.py). This labels every champion-turn with the branch of
`Bot.play_turn` that took it (dead, channel, retreat, heal, disengage, capture,
bank, shop, combat, travel, approach, idle...) and records separately whether
the turn landed a hit on a camp or on a champion. Every 25 rounds each
champion prints its cumulative counts:

    TL <round> <champion> turns=N hit_camp=N hit_champ=N <label>=N ...

`timeprofile.py` reads them back out of a bench folder's replay bundles. The
logger is behaviour-neutral in its decisions, but the extra work shifts fuel
suspensions, so its games are a sample of the bot's play, not a replay of it.

    mktimelog.py gs97_timelog                 # from gs93_bh, version 97's twin
    mktimelog.py NAME --base OTHER_BOT
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"

# A hit on a camp or a champion this turn, whichever branch landed it.
COMBAT_HOOK = '''


# --- time-use logger -----------------------------------------------------------
hits = {'camp': False, 'champion': False}
_untimed_fight = fight


def fight(target, nearby=()):
    acted = _untimed_fight(target, nearby)
    if acted:
        hits['camp' if isinstance(target, bc.Camp) else 'champion'] = True
    return acted
'''

WRAPPER = '''    def play_turn(self):
        """Time-use logger: label this turn, count it, print every 25 rounds."""
        self.label = 'unlabelled'
        combat.hits['camp'] = combat.hits['champion'] = False
        try:
            self._play_turn()
        except Exception as error:
            if type(error).__name__ == 'Replan':
                self.label = 'replan/' + self.label
            raise
        finally:
            counts = self.__dict__.setdefault('time_counts', {})
            counts['turns'] = counts.get('turns', 0) + 1
            counts[self.label] = counts.get(self.label, 0) + 1
            for kind in ('camp', 'champion'):
                if combat.hits[kind]:
                    key = 'hit_' + ('camp' if kind == 'camp' else 'champ')
                    counts[key] = counts.get(key, 0) + 1
            now = bc.round_number()
            if now // 25 != self.__dict__.get('time_printed', -1):
                self.time_printed = now // 25
                print('TL %d %s %s' % (now, bc.me().champion_name(),
                                       ' '.join('%s=%d' % kv for kv in sorted(counts.items()))), flush=True)

    def _play_turn(self):
'''

# (file, old, new): labels for the branches greatsage's lineage leaves unlabelled.
LABELS = [
    ("bot.py", "        self.last_state = label\n",
     "        self.last_state = label\n        self.label = label\n"),
    ("bot.py", "            else:\n                self.team.claim()\n            return\n"
               "        if not (me.can_move() or me.can_attack() or me.can_cast()):\n            return\n",
     "            else:\n                self.team.claim()\n            self.status('channel')\n            return\n"
     "        if not (me.can_move() or me.can_attack() or me.can_cast()):\n            self.status('inert')\n            return\n"),
    ("bot.py", "        if at_spawn and me.health() < me.max_health():\n            self.team.claim()\n            return\n",
     "        if at_spawn and me.health() < me.max_health():\n            self.team.claim()\n            self.status('spawn_heal')\n            return\n"),
    ("bot.py", "            self.team.claim()\n            self.objective = None\n            turn.check()\n            me.recall()\n            return\n"
               "        enemy_spawn",
     "            self.team.claim()\n            self.objective = None\n            self.status('shop')\n            turn.check()\n            me.recall()\n            return\n"
     "        enemy_spawn"),
    ("bot.py", "        self.objective = objective\n        if objective is None:\n            self.team.claim()\n",
     "        self.objective = objective\n        if objective is None:\n            self.status('idle')\n            self.team.claim()\n"),
    ("bot.py", "            self.team.claim()\n            self.progress.reset()\n            return\n",
     "            self.team.claim()\n            self.progress.reset()\n            self.status('blocked')\n            return\n"),
    ("bot.py", "        targets = observed\n        if not targets:\n            nav.move_to(objective.spawns)\n            return\n",
     "        targets = observed\n        if not targets:\n            self.status('travel')\n            nav.move_to(objective.spawns)\n            return\n"),
    ("bot.py", "        self.status('farm')\n", "        self.status('approach')\n"),
]


def build(name: str, base: str) -> None:
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WS / "bots" / base, dst, ignore=shutil.ignore_patterns("__pycache__", ".cambc"))
    src = dst / "src"
    texts = {f: (src / f).read_text() for f in ("bot.py", "combat.py", "main.py")}
    for f, old, new in LABELS:
        if texts[f].count(old) != 1:
            sys.exit(f"{f}: anchor found {texts[f].count(old)} times: {old[:60]!r}")
        texts[f] = texts[f].replace(old, new, 1)
    if texts["bot.py"].count("    def play_turn(self):\n") != 1:
        sys.exit("play_turn anchor")
    texts["bot.py"] = texts["bot.py"].replace("    def play_turn(self):\n", WRAPPER, 1)
    texts["combat.py"] = texts["combat.py"].rstrip("\n") + COMBAT_HOOK
    texts["main.py"] = re.sub(r'print\("BOTTAG [^"]+", flush=True\)', f'print("BOTTAG {name}", flush=True)',
                              texts["main.py"])
    for f, t in texts.items():
        (src / f).write_text(t)
    # The escort and boss controllers override farm(); label their turns too.
    for f, cls in (("escort.py", "escort"), ("boss.py", None)):
        p = src / f
        if p.exists() and cls:
            t = p.read_text()
            anchor = "    def farm(self, me, enemies):\n"
            if t.count(anchor) == 1:
                p.write_text(t.replace(anchor, anchor + f"        self.status('{cls}')\n", 1))
    for p in src.glob("*.py"):
        ast.parse(p.read_text())
    print(f"  {name}: from {base}, parses, tagged")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--base", default="gs93_bh")
    a = ap.parse_args()
    build(a.name, a.base)
