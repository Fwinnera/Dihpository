"""Camp utility and score-aware banking; cached terrain metadata is public."""
import cambc as bc
from cambc import game_map as gm
import config
import turn
from navigation import distance


def should_bank(enemies):
    me = bc.me()
    gems = me.gem_count()
    if gems <= 0:
        return False
    ours = bc.global_submitted_gems(bc.Team.ALLY)
    theirs = bc.global_submitted_gems(bc.Team.ENEMY)
    return (gems >= config.BANK_GEMS
            or ours + gems >= bc.constants.WINNING_GEMS
            or bc.round_number() >= config.LATE_GAME_ROUND
            or theirs >= 900
            or (enemies and me.health() < me.max_health() * 0.75))


def prepare(groups):
    """One-time public geometry/design cache; never cache unseen current health."""
    return [(g, tuple((p.x, p.y) for p in g.spawn_tiles().positions()),
             sum(c.base_stats().base_health for c in g.camps()),
             g.gem_value() + g.gold_value() * 0.15,
             any(c.is_monolith() for c in g.camps())) for g in groups]


def choose_group(metadata, me, remembered_respawns, current):
    position = me.position()
    x, y = position.x, position.y
    damage = max(1, me.strength() * 1.15)
    now = bc.round_number()
    capture = bc.constants.CAPTURE_TIME
    roster_size = max(1, bc.draft.team_size())
    kind = me.champion_name()
    role = {bc.ChampionType.RYTH: 0, bc.ChampionType.VENDETTA: 1,
            bc.ChampionType.WILLOW: 2}.get(kind, kind) % roster_size
    ranked = []
    for index, (group, tiles, hp, value, monolith) in enumerate(metadata):
        handle = group.__index__()
        if (monolith and not config.ALLOW_MONOLITH) or remembered_respawns.get(handle, 0) > now:
            continue
        travel = min(max(abs(x-px), abs(y-py)) for px, py in tiles)
        score = (travel + hp/damage + capture) * 100 / max(1, value)
        if handle == current:
            score -= 3
        if index % roster_size != role:
            score += config.ROLE_SPREAD_PENALTY
        ranked.append((score, index, travel))
    ranked.sort()
    visible = bc.vision.visible_tiles()
    best, best_score = None, float('inf')
    # Only four plausible objectives get live-state queries. The old version
    # queried every monster and frequently exhausted a turn before moving.
    for score, index, travel in ranked[:4]:
        turn.check()
        group, tiles, hp, value, monolith = metadata[index]
        spawns = group.spawn_tiles()
        if not (spawns & visible).is_empty():
            state = group.state()
            if isinstance(state, gm.CampGroupRespawning):
                remembered_respawns[group.__index__()] = now + state.timer
                continue
            if isinstance(state, gm.CampGroupRewardAvailable):
                score = (travel + capture) * 100/max(1,value) - 20
        if score < best_score:
            best, best_score = group, score
    return best
