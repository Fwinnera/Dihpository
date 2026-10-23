#!/usr/bin/env python3
"""Build the fixes from the #1 analysis, each one change on version 93's tagged twin.

    mkfixes.py                     # builds every variant below
    mkfixes.py gs93_hurt60 ...     # or just the named ones
    mkfixes.py gs93_combo=hurt60+willow_farm+travel60   # stacked

Base: ws/bots/gs_seelie_dis050, which is the live version 93 plus a BOTTAG, so
every variant compares game for game with its full-pool results.
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
BASE = "gs_seelie_dis050"

HURT = '''        # A hurt champion leaves when an enemy champion is within reach, instead of
        # fighting on down to 30%. We died 22.5 times a game over 510 ladder games;
        # the #1 team, which spends 2.5 times as much of the game farming, dies 7.1
        # times. A healthy champion still returns fire: removing the proximity
        # accept outright cost 159 gems, because champions stopped fighting back.
        for enemy in enemies:
            turn.check()
            if nav.distance(position, enemy.position()) <= config.HURT_RADIUS:
                threshold = max(threshold, config.HURT_RETREAT)
                break
'''
HURT_CFG = '''# Retreat threshold while an enemy champion is within HURT_RADIUS tiles.
HURT_RETREAT = {h}
HURT_RADIUS = 5
'''
ESCORT_OLD = '''                if ally.health() < ally.max_health() * 0.7:
                    priority -= 1
'''
ESCORT_NEW = '''                # Follow a farmer, not a fight. Moving towards hurt allies took the
                # team's lowest-health champion into the fights that hurt them:
                # Willow died 5.5 times a game for 0.3 kills. A leader with an enemy
                # champion near it is now the last choice instead of the first.
                for enemy in bc.vision.champions(bc.Team.ENEMY):
                    turn.check()
                    if enemy.is_alive() and nav.distance(ally.position(), enemy.position()) <= 5:
                        priority += 2
                        break
'''
WILLOW_OLD = '''    if bc.me().champion_name() == bc.ChampionType.WILLOW:
        from escort import EscortBot
        return EscortBot()
'''
WILLOW_NEW = '''    # Willow farms like everyone else. As an escort she banked 4% of the team's
    # gems and spent 5.7% of the game farming; heal_allies still runs every turn.
'''
TRAVEL_CFG = '''# Weight of travel in camp choice. The #1 team farms at depth 0.37-0.45 between
# the bases and banks at the central altar; we farmed at 0.11-0.21 and banked at
# home, because travel dominated the cost. Below 1, richer camps further out win.
TRAVEL_WEIGHT = {w}
'''


def edit(path: Path, old: str, new: str, count: int = 1) -> None:
    t = path.read_text()
    if t.count(old) != count:
        sys.exit(f"{path.name}: expected {count} of {old[:50]!r}, found {t.count(old)}")
    path.write_text(t.replace(old, new))


def apply(src: Path, change: str) -> None:
    """One change, by its variant name without the gs93_ prefix."""
    cfg = src / "config.py"
    m = re.fullmatch(r"hurt(\d+)", change)
    if m:
        edit(src / "bot.py", "        position = me.position()\n        camp_pressure = ",
             "        position = me.position()\n" + HURT + "        camp_pressure = ")
        cfg.write_text(cfg.read_text() + HURT_CFG.format(h=int(m.group(1)) / 100))
    elif change == "willow_farm":
        edit(src / "policy.py", WILLOW_OLD, WILLOW_NEW)
    elif change == "escort_safe":
        edit(src / "escort.py", ESCORT_OLD, ESCORT_NEW)
    elif re.fullmatch(r"travel(\d+)", change):
        w = int(change[len("travel"):]) / 100
        st = src / "strategy.py"
        edit(st, "        estimate = cost + (travel + risk) * 100 / max(1, value) + bias",
             "        estimate = cost + (travel * config.TRAVEL_WEIGHT + risk) * 100 / max(1, value) + bias")
        edit(st, "        score = (travel + clear + capture + risk) * 100 / max(1, value) + bias",
             "        score = (travel * config.TRAVEL_WEIGHT + clear + capture + risk) * 100 / max(1, value) + bias")
        edit(st, "            score = (travel + capture) * 100 / max(1, value) - 15",
             "            score = (travel * config.TRAVEL_WEIGHT + capture) * 100 / max(1, value) - 15")
        cfg.write_text(cfg.read_text() + TRAVEL_CFG.format(w=w))
    else:
        sys.exit(f"unknown change {change}")


def build(name: str, changes: list[str] | None = None) -> None:
    """gs93_<change> builds one change; pass `changes` to stack several."""
    changes = changes or [name[len("gs93_"):]]
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WS / "bots" / BASE, dst, ignore=shutil.ignore_patterns("__pycache__", ".cambc"))
    src = dst / "src"
    for change in changes:
        apply(src, change)
    main = src / "main.py"
    main.write_text(re.sub(r'print\("BOTTAG [^"]+", flush=True\)', f'print("BOTTAG {name}", flush=True)',
                           main.read_text(), count=1))
    for p in src.glob("*.py"):
        ast.parse(p.read_text())
    print(f"  {name}: {' + '.join(changes)}; parses, tagged")


ALL = ["gs93_hurt60", "gs93_willow_farm", "gs93_escort_safe", "gs93_travel60", "gs93_travel40"]
if __name__ == "__main__":
    # mkfixes.py NAME=change+change ... stacks changes into one build.
    for n in sys.argv[1:] or ALL:
        if "=" in n:
            name, spec = n.split("=", 1)
            build(name, spec.split("+"))
        else:
            build(n)
