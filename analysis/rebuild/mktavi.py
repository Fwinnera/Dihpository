#!/usr/bin/env python3
"""Draft Tavi ahead of Ryth on solo maps (ab3-line bot).

    mktavi.py BOTDIR

Why (GROUND-UP-PLAN.md, "UK-level teams' style"): both teams at the UK top-8 line draft Tavi in most
games (QS2isLaw Prism + Ryth + Tavi + VV + Vendetta; policy wonk Marcella + Prism + Tavi + Varg +
Willow). Tavi buys shards anywhere, and our shop() already buys whenever can_buy allows, so a Tavi
shops on the move with no trip home. Our Ryth is our weakest champion on the lab (582 gold and
4 deaths a game against the field's Ryth's 1,031 and 2). The solo-map order becomes Varg,
Vendetta, Vesper Vale, Tavi, Marcella, Ryth, Willow, ...: five-pick maps swap Ryth for Tavi,
four-pick maps take Tavi in Ryth's place, three-pick maps are unchanged. Party maps unchanged.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
f = src / "draft.h"
t = f.read_text()
old = "        order = {D::varg, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};"
new = "        order = {D::varg, D::vendetta, D::vesper_vale, D::tavi, D::marcella, D::ryth, D::willow, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};"
if t.count(old) != 1:
    sys.exit("draft.h: solo order not found")
f.write_text(t.replace(old, new))
print("patched", src)
