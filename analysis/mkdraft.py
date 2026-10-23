"""Draft-order variants. Only roster.py's preference tuple changes."""
import ast, shutil, sys
from pathlib import Path

WS = Path("/Users/faeezaullyar/Claude/battlecode/ws")
SRC = WS / "bots/greatsage"
OLD = open(SRC / "src/roster.py").read().split("\n")[2]
assert OLD.startswith("DRAFT_ORDER = ("), OLD[:40]

D = "bc.ChampionDraft."
def order(names, note):
    body = ", ".join(D + n for n in names)
    return f"# {note}\nDRAFT_ORDER = ({body})"

FIELD = """Measured over 470 ladder games: the opponents field Vesper Vale in 71% of
# games and Heart of Ruin in 70%, where this order ranked them eighth and twelfth of
# twelve and we fielded them in 3%. Both teams can field the same champion -- Ryth is
# 75% ours and 70% theirs -- so those rates are the field's preference, not what our
# own picks left them. Willow is 97% ours against 12% theirs."""

VARIANTS = {
    # The field's own top five, in its order.
    "gs_draft_field": order(
        ["VESPER_VALE", "HEART_OF_RUIN", "RYTH", "VENDETTA", "MARCELLA", "VARG",
         "WILLOW", "TAVI", "CASSI_AND_ISSAC", "REN", "STELLAR", "PRISM"], FIELD),
    # One change: Willow out, Vesper Vale in.
    "gs_draft_vv": order(
        ["MARCELLA", "VENDETTA", "VESPER_VALE", "VARG", "RYTH", "WILLOW", "TAVI",
         "CASSI_AND_ISSAC", "REN", "STELLAR", "PRISM", "HEART_OF_RUIN"], FIELD),
    # One change: Willow out, Heart of Ruin in.
    "gs_draft_hor": order(
        ["MARCELLA", "VENDETTA", "HEART_OF_RUIN", "VARG", "RYTH", "WILLOW", "TAVI",
         "CASSI_AND_ISSAC", "REN", "STELLAR", "PRISM", "VESPER_VALE"], FIELD),
    # Both of the contested pair in, Willow and Varg out.
    "gs_draft_both": order(
        ["MARCELLA", "VENDETTA", "VESPER_VALE", "HEART_OF_RUIN", "RYTH", "VARG",
         "WILLOW", "TAVI", "CASSI_AND_ISSAC", "REN", "STELLAR", "PRISM"], FIELD),
}

for name, new in VARIANTS.items():
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)
    p = dst / "src/roster.py"
    t = p.read_text()
    if OLD not in t:
        sys.exit(f"{name}: draft order line not found")
    p.write_text(t.replace(OLD, new, 1))
    for q in (dst / "src").glob("*.py"):
        ast.parse(q.read_text())
    m = dst / "src/main.py"
    m.write_text(m.read_text().replace(
        "def main():", f'def main():\n    print("BOTTAG {name}", flush=True)\n', 1))
    ast.parse(m.read_text())
    print(f"  {name}: parses, tagged")
