# apex: a C++ bot modelled on the #1 team (prism best girl)

Owner's request (2026-10-24): a new C++ bot with #1's behaviour, #1's
characters and #1's emblem choices, using every cue available. Built on the
trusted plumbing of `ws/bots/gs_cpp93_party` (CLOUD's C++ port of v93 plus the
party rule; +39.5 gems over v93 on the full pool): pathfinding with dash and
crystal routes, claims and collector protocol, fuel guard, and the shop and
capture mechanics. Everything below replaces the decision layer.

## Sources

60 of #1's ranked games (`ws/bench/top1`, `analysis/mine_top1.py`), plus the
engine's design data (champion stats, abilities and passives, read inside a
match) and the game constants.

## Draft

#1 picks Prism first in every game. Most common orders: Prism > Vesper Vale >
Marcella > Ryth > Heart of Ruin (17 of 60); Prism > Marcella > Vendetta > Heart
of Ruin > Vesper Vale (13); Prism > Vesper Vale > Heart of Ruin on 3-champion
maps. apex: **Prism, Vesper Vale, Marcella, Ryth, Heart of Ruin**, then
Vendetta, on every map.

## Roles, from the passives and the per-champion record

| champion | engine facts | #1's record | apex role |
|---|---|---|---|
| Prism | CC + area damage, both focus-scaled; passive: focus per carried gem | farms deepest (0.43), mean carried 80, peak 196; 0.7 deposits a game, 82% in the last 50 rounds; 10 monolith clears | **finisher**: keeps its gems (they are its damage) and deposits when the team can win, at the end, at a cap, or in danger |
| Vesper Vale | attack reset + dash; passive: extra gold | most camp damage (38k) and champion damage (12k), most gold; 6.2 deposits at ~33; 17 monolith clears | main farmer and raider; banks normally |
| Marcella | attack reset + damage x2.0 | 5.5 deposits at ~30; 11 monolith clears | bruiser farmer; banks normally |
| Heart of Ruin | self shield (5 rounds) + dash; passive: up to +50% damage at full missing health | takes the most damage (18.3k), 13,230 self-shielding a game; 3.8 deposits | **tank**: shields below 90% health, retreats only at 15%, no heal-recall |
| Ryth / Vendetta | area damage + attack reset / attack reset + dash | 2-3 deposits at ~20-26 | farmers |

## Emblems, in #1's purchase order (then Bruiser for the rest)

- Prism: Durability:Health > Monster:Focus > Jungle:Health > Bruiser:Health > Home:Health
- Vesper Vale: Jungle:Strength > Bruiser:Strength > Bruiser:Health > Durability:Health
- Marcella: Bruiser:Strength > Bruiser:Health > Bruiser:Focus
- Heart of Ruin: Jungle:Focus > Bruiser:Health > Durability:Health > Bruiser:Focus
- Ryth: Jungle:Strength > Bruiser:Health > Durability:Health
- Vendetta: Jungle:Strength > Bruiser:Strength > Bruiser:Health > Durability:Health

No Treasure; Power only as #1's Ryth sometimes does. The late shop buys Bruiser
(seven stat points for 150 gold, against Power's six).

## Macro behaviour

- **Monolith raids** late, by several champions: #1 clears 0.7 a game, median
  round 993, three or more champions at once. apex: monolith groups become
  eligible from round 900 on maps where monoliths hold at least half the
  gems, costed for 1 + max(claimed, 2) raiders, and a claimed raid pulls
  teammates in (v100's `raid900` + `monogate`).
- **Bank at the central altar**, as #1 does (deposit depth about 0.5): banking
  goes to the nearest altar, and a nearby enemy-locked altar beats a free one
  more than 6 tiles further away (v100's `lockbreak`).
- **Heal-recall** below 60% health when recall is safe and the champion is not
  capturing (v97), except Heart of Ruin.
- **Disengage** from lost fights at a local strength ratio of 0.5 (v93).

## Acceptance

Against v100 (the live Python bot) on the four distinct local opponents, and
head to head against v100. The bar is the same as for any change: better on
gems with at least 90% one-sided confidence (clustered), win rate not worse.
If apex falls short, ablate: draft only, then each role, to find what costs.

## Result (2026-10-24)

Not competitive. Head to head against v100 (80 games each): apex v1 19 of 80,
-311 gems a game; apex v2 (per-map draft, finisher that also deposits when the
enemy nears 1,000) 24 of 80, -254; best variants (v2 without the tank, or
without tank and finisher) 29-32 of 80, -208. Four distinct opponents, v1:
-210.8 (clustered z -6.21). The C++ port with every #1 switch off (`cv100`)
matches v100 exactly (37 of 80, -14; four opponents -8.1, z -0.40), so the loss
is the #1 layer: about -200 from the roster alone. Details and mechanisms in
`GROUND-UP-PLAN.md`, section "apex".
