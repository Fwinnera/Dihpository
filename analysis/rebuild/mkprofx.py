#!/usr/bin/env python3
"""Add two fields to a profiler bot's PF line (run after mkprof.py): visible enemy
champions within 6 tiles and allies within 5, so retreats and deaths can be read with
their local odds.  PF round type label x y hp maxhp gems gold group ENEMIES ALLIES

    mkprofx.py BOTDIR
"""
import sys
from pathlib import Path

f = Path(sys.argv[1]) / "src" / "main.cpp"
t = f.read_text()
old = "                              << me.gold_count() << ' ' << prof::group << '\\n';\n"
new = ("                              << me.gold_count() << ' ' << prof::group << ' ';\n"
       "                    int foes = 0, friends = 0;\n"
       "                    if (me.is_alive()) {\n"
       "                        for (const auto& e : bc::vision::champions(bc::team::enemy))\n"
       "                            if (e.is_alive() && distance(e.position(), me.position()) <= 6) ++foes;\n"
       "                        for (const auto& a : bc::champions(bc::team::ally))\n"
       "                            if (a.is_alive() && a.is_visible() && !same(a, me) && distance(a.position(), me.position()) <= 5) ++friends;\n"
       "                    }\n"
       "                    std::cout << foes << ' ' << friends << '\\n';\n")
if t.count(old) != 1:
    sys.exit("PF print line not found; run mkprof.py first")
f.write_text(t.replace(old, new))
print("patched", f)
