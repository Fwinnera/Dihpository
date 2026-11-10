# Top-50 push: brief for the cloud session (written 10 Nov 2026, 08:05Z, on the owner's Mac)

The owner's words (10 Nov): "critique this bot, see what can we improve and i want to DRASTICALLY improve
this bot, i want top 50 minimum, WOW me", then "lets run this on cloud" (the laptop is going off).

## 1. Clock and standing

- **Lock: Tue 10 Nov 23:59 GMT** (the site: all deadlines are UK time; a snapshot is taken at the lock). The UK
  qualifier on 11 Nov is seeded from the ladder.
- **Ladder, 9 Nov 20:04Z** (829 teams): we are **rank 227, rating 1,753**, 50th of 192 UK teams.
  Rating at rank 50: **2,165**; rank 100: 2,002; rank 150: 1,888; rank 200: 1,793. UK top-8 line: 2,189.
  Public API: `https://2026a.battlecode.co.uk/api/v1/ladder?page=N&pageSize=100&pageCount=1&snapshot=latest&category=all`.
- Top 50 needs about **+410 rating in under 16 hours**. Three weeks of work moved this bot from about 1,655 to
  1,753. Say so plainly to the owner. A stronger bot also needs ranked games to move the rating (about 29 an
  hour), so **a gain uploaded at noon counts for more than the same gain at 18:00**.
- **Live: v183**, uploaded on the website by a teammate (9 Nov), team in **follow-newest** mode: any upload
  goes live at once. v183 = v180 (mg4) + Tavi in Ryth's draft slot + `threat_dps()` (spell output counted in
  threat) + Vesper Vale's build Treasure > Hunter > Power. Source rebuilt byte for byte:
  `ws/bots/v183_submit/src` (and `ws/bots/v182_submit/src`); `analysis/rebuild/mkv183.py` builds both from mg4.
  **v183 has never been lab-tested.**
- **Login:** neither the Mac's CLI nor the browser pane is signed in. The cloud session needs the owner to
  approve `cambc login` (it prints a link). Until then: build and test locally only.

## 2. Rules digest (handbook, read 10 Nov; Patch 4.0.0 numbers)

- **Win:** first to 1,000 tributed gems, else most gems at round 2,000 (then gold earned, then kills).
- **A turn:** walk 1 tile (8 directions) + one basic attack (damage = Strength) + one ability cast.
  **Ranged champions walk OR attack**, not both (an attack reset can restore the attack). Melee range 1,
  ranged 3. Both ability slots have 8-round cooldowns; one cast a turn. Spells deal multiplier x Focus.
- **Camps** (asleep until hit; an awake camp hits the nearest champion in range every turn; sleeps after 2
  turns with no target):

      Monster       Health  Strength  Range  Gold  Gems  Respawn
      Wolf           1,350     20       3     40     4     40
      Elk            2,400     60       4     90    15     60
      Golem          5,000    120       4    160    36     80
      Gem cluster      120      0       0      0     7     50
      Gold cluster     120      0       0     20     0     50
      Monolith      20,000    200       5    300   200    150

  A group is the set of cardinally connected monsters. Clear all of it, then stand on a monster tile for 5
  turns; the reward is split evenly between the champions standing there.
- **Tribute:** stand beside an altar; the channel is gems / 10 turns, rounded up. Damage does not cancel it; a
  stun does, and so does an enemy altar lock (10 gold consumable, 5 basic attacks to break).
- **Death:** respawn after 60 rounds; the killer takes every carried gem and 100 gold. Killed by a camp: the
  gems are lost. **Recall:** 5 turns, cancelled by any damage or a stun; spawn tiles heal and are the shop.
  Items can also be bought while dead.
- **Vision:** 8 tiles, ray cast (walls and bushes block). **Not shared between allies.** One free ward each
  (vision 6, placed within 2 tiles, recharges in 10 turns). **Shared memory: 8 bytes for the whole match**
  (ours: 10 bits a champion, the claimed camp group, so 4 bits are free), plus 1,024 bytes written in the draft.
- **Fuel:** 100k a turn for C++ (the first draft turn 100x, the first play turn 2x). The draft sees the whole map.
- **Items:** a shard costs 30 gold and adds the champion's growth in that stat; five combine into an emblem.
  Power = 6 shards' worth, no passive. Monster +15% damage to camps. Jungle -30% damage from camps.
  Durability -10% damage taken. Skirmish **+10% damage to champions** (was 5%). Hunter +50 gold a kill.
  Treasure +10% gold. Bruiser 5 + 1 + 1. Prospector +25% of your share of cluster rewards. Capture caps the
  capture timer at 3. Home: recall in 3 turns. Tribute: 33% shorter tribute. Collectors +1% damage per
  completed family. Greed: 25 shards (750 gold) give 40. Passives do not stack; there is no item cap.
- **Champions** (health / strength / focus, growth per shard in brackets; slot 0, slot 1):

      Cassi (ranged; drafted with Issac)  600 (+65) / 30 (+3) / 100 (+13)   2xFocus hit, range 4, no walking; 1-round stun, range 4
      Issac (melee; drafted with Cassi)   900 (+80) / 45 (+3) / 100 (+10)   attack reset; dash
      Heart of Ruin (melee)             1,000 (+100) / 30 (+3) / 80 (+9)    1.5xFocus shield for 5 turns; dash 2 tiles, 1.5xFocus
                                                                            area hit and 1-turn stun on landing
      Marcella (melee, stun-immune)     1,200 (+100) / 40 (+3.5) / 60 (+10) reset whose next attack stuns; 2xFocus hit, range 4, no walking
      Prism (ranged)                      700 (+65) / 35 (+2.5) / 90 (+8)   damage and stun; area damage
      Ren (melee)                         900 (+100) / 35 (+5) / 100 (+9)   damage and stun; dash
      Ryth (melee)                      1,200 (+100) / 45 (+4.5) / 100 (+10) area stun; attack reset
      Stellar (ranged)                    650 (+65) / 30 (+3.5) / 85 (+8.5) single-target damage; area damage
      Tavi (ranged, shops anywhere)       900 (+75) / 45 (+5) / 110 (+10)   attack reset; damage and stun
      Varg (melee, splash attacks)      1,000 (+100) / 50 (+5) / 100 (+10)  attack reset; self-shield
      Vendetta (melee, kills reset CDs)   900 (+100) / 65 (+6) / 100 (+10)  attack reset; dash
      Vesper Vale (ranged, +33% gold)   1,000 (+100) / 35 (+5) / 100 (+10)  attack reset; dash
      Willow (ranged)                     700 (+50) / 55 (+3) / 140 (+5)    ally heal; attack reset

  **Cassi & Issac are one pick and two bodies** (if either dies, both die; one kill reward). Heart of Ruin
  deals up to +50% damage with missing health.
- **Pick rates, last 50 games of each team (9 Nov):** ranks 1-10: Heart of Ruin 81%, Cassi & Issac 76,
  Marcella 60, Vesper Vale 59. Ranks 51-100: Marcella 88, Heart of Ruin 72, Vendetta 68, Vesper Vale 68,
  Ryth 52, Cassi & Issac 28, Varg 25, Willow 22. **Us:** Varg 100, Vendetta 100, Vesper Vale 90, Tavi 78,
  Marcella 54.

## 3. Critique of v183 (from reading the code; check each against replays before building on it)

1. **It is five soloists.** Each champion picks its own camp from a 10-bit reservation; nothing says where
   teammates or enemies are (vision is not shared and we never use the spare bits or wards for it). Ladder
   data: our champions have no teammate within 5 tiles for 57% of turns (ladder teams 42%), we die 16.6 times
   a game (lab opponents 7.7, top teams about 5) and mostly outnumbered, 1v2 and 1v3.
2. **Solo farming is a commute.** An elk has 2,400 health and hits for 60: Vendetta (65 strength) needs about
   33 turns and takes about 2,000 damage, twice her health. `HEAL_RECALL = 0.60` sends a champion home after
   losing 40% of its health: 5 turns of recall, the heal, and the walk back. Two or three champions on one
   camp cut the time and the damage per head by that factor. Top teams farm 43% more per living champion.
3. **Running away does not work in this game, and 81-84% of our deaths come while retreating.** Melee
   champions walk and attack in the same turn at our speed, so a champion that turns its back takes every
   hit and deals none. The low-health retreat (30% / 43%) and the disengage rule fire after contact. The
   decision has to come before contact (numbers, wards), or the champion should trade until it dies.
4. **The draft ignores the map and the meta.** Fixed list: Varg, Vendetta, Vesper Vale, Tavi, Marcella.
   Heart of Ruin is last and Cassi & Issac (a sixth body) eighth, so neither is ever picked. The draft turn
   has 100x fuel and sees the whole map.
5. **Items ignore most of the shop.** Hunter first (+50 gold a kill, at about 1.6 kills a champion a game),
   then 150 gold of Durability health, then Jungle; no Monster (+15% camp damage), no Skirmish, no Focus on
   anyone but Willow although every spell scales with Focus.
6. **Ranged champions do not kite** (attack at range 3, step away from melee), targets are chosen per
   champion (no shared focus fire), and stuns are valued by damage prevented, not by the tribute or recall
   they cancel (only a flat +120 on a tributing target).
7. **Maps:** party controller (BossBot) on monolith-gated maps only; everything else is the solo controller.

Tested before and level or worse (do not repeat without a new reason; details in `docs/IMPROVE-PROMPT.md`
section 5): Heart of Ruin for Ryth (77 v 86), Tavi for Ryth (78), escorts and two-pair squads, assist a
teammate (62 v 73), Bruiser strength builds, heal-recall 70%, recall variants. Those were single swaps
inside the solo controller; nobody has tested Cassi & Issac, Monster-first or Focus builds, or a meta five
together with its items.

## 4. Plan for the hours left

Rules that still hold: `docs/IMPROVE-PROMPT.md` section 3 (never use credentials from chat; README ladder
lock around every platform action; only untagged, smoke-tested `_submit` builds; re-pin after every submit;
notes of 80 characters or fewer; 50 match groups an hour; write the keep rule in `GROUND-UP-PLAN.md` before
the result). The owner has given durable permission to push and to test as much as needed.

1. **Set up** (`analysis/cloud/README.md`, `analysis/cloud/e3/`): cambc **5.0.1**, a fresh workspace, the
   toolchain by curl, Node 22 for the decoders. Ask the owner to approve `cambc login` straight away.
2. **Baseline today's live bot:** lab v183 (three sets, `--from pm_best`, `pm_best_s2`, `pm_best_s3`;
   baselines e3v166 86, mg4 78, tv1 78 of 150). If v183 is clearly below mg4, re-pin v180 first.
3. **Cheap, big levers first, one lab arm each (36 minutes of quota an arm):**
   a. Cassi & Issac in the five (six bodies). Check the 60-bit reservation table and the duo's retreat.
   b. Monster-first strength build; Skirmish as the fourth emblem (`analysis/rebuild/mkitems5.py`; Vesper
      Vale's own build needs the Skirmish entry by hand); Focus builds for focus-scaling picks.
   c. A meta five (Heart of Ruin, Marcella, Vesper Vale, Vendetta, Cassi & Issac) only with its items.
4. **Study before the structural bet:** download 20 recent games of teams ranked 30-80 and 20 of our losses,
   decode with `read3.mjs` / `actions3.mjs`, and compare rounds 1-400: who farms what, in what company, when
   they shop, what they buy. Then build **one** of: pair farming on elk and golem groups (leader claims,
   partner follows the claim), or fight-or-trade instead of the late retreat.
5. **Ship early, keep the best pinned.** Promote on a lab win of 12 or more over the best arm of the same
   sets, and aim opponents higher (ranks 80-150) for anything that passes. Pin the final choice by 18:00Z
   unless the owner says otherwise; confirm `Live:`; update the README lock and `GROUND-UP-PLAN.md`.
6. **Report honestly:** the rank reached, what was tested, what was kept and why.
