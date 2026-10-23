"""Select useful casts, preserve resets, and fight only for a concrete gain."""
import cambc as bc
import config
import turn
from navigation import distance, around


def visible_camps(camps):
    result = []
    for camp in camps:
        turn.check()
        if (camp.is_visible() and bc.vision.has_camp(camp.spawn_position())
                and camp.health() > 0):
            result.append(camp)
    return result


def choose_camp(camps):
    """Score splash targets in O(9N), without live-position queries in a nested loop."""
    turn.check()
    me = bc.me()
    origin, radius = me.position(), me.attack_range()
    ox, oy = origin.x, origin.y
    rows = []
    for camp in camps:
        turn.check()
        if not camp.is_visible() or not bc.vision.has_camp(camp.spawn_position()):
            continue
        hp = camp.health()
        if hp > 0:
            p = camp.spawn_position()  # Camps never move; this is public static data.
            rows.append((camp, p.x, p.y, hp))
    if not rows:
        return None
    occupied = {(x, y) for _, x, y, _ in rows}
    splash = me.champion_name() == bc.ChampionType.VARG
    def score(row):
        _, x, y, hp = row
        gap = max(abs(ox - x), abs(oy - y))
        neighbours = (sum((x + dx, y + dy) in occupied for dx in (-1, 0, 1)
                          for dy in (-1, 0, 1)) if splash else 0)
        return (gap > radius, -neighbours, hp)
    turn.check()
    return min(rows, key=score)[0]


def live(target):
    turn.check()
    if isinstance(target, bc.Camp):
        return bc.vision.has_camp(target.spawn_position())
    return target.is_visible() and target.is_alive()


def attack(target):
    me = bc.me()
    if (me.can_attack() and live(target) and target.health() > 0
            and me.attack_tiles().is_set(target.position())):
        turn.check()
        me.attack(target)
        return True
    return False


def heal_allies(allies):
    turn.check()
    me = bc.me()
    for ability in me.abilities():
        if not ability.is_heal() or not ability.is_ready() or not turn.may_cast(ability):
            continue
        mask = ability.valid_tiles()
        targets = [a for a in allies if a != me and a.is_alive() and a.is_visible()
                   and mask.is_set(a.position())
                   and a.max_health() - a.health() >= config.HEAL_MIN_MISSING]
        if targets:
            target = min(targets, key=lambda a: a.health() / a.max_health())
            turn.check()
            return ability.use(target)
    return False


def fight(target, nearby=()):
    me = bc.me()
    if not live(target) or target.health() <= 0:
        return False
    enemy = isinstance(target, bc.Champion)
    position = target.position()
    in_attack = me.can_attack() and me.attack_tiles().is_set(position)
    choices = []
    for ability in me.abilities():
        turn.check()
        if not ability.is_ready() or not turn.may_cast(ability):
            continue
        if ability.is_attack_reset():
            if in_attack and target.health() > me.strength():
                choices.append((me.strength(), ability, None))
            continue
        if ability.is_shield():
            incoming = target.strength()
            if incoming and me.health() < me.max_health() * 0.70 and distance(me.position(), position) <= 4:
                choices.append((min(ability.shield_amount(), incoming * 4) * 0.65, ability, None))
            continue
        if not (ability.is_damage() or ability.is_aoe_damage() or ability.is_cc()):
            continue
        if enemy and not ability.can_target_enemies():
            continue
        if not enemy and not ability.can_target_camps():
            continue
        amount = ability.damage_amount(target) if enemy else ability.damage_amount()
        control = 0
        if ability.is_cc() and (not enemy or target.champion_name() != bc.ChampionType.MARCELLA):
            if enemy:
                control = target.strength() * 0.8 + (120 if target.is_submitting_gems() else 0)
            elif target.strength() and distance(me.position(), position) <= target.attack_range():
                control = target.strength() * 0.8
        if not amount and not control:
            continue
        mask = ability.valid_tiles()
        if ability.can_target_ground():
            radius = int(getattr(ability.info(), 'radius', 1))
            units = [u for u in nearby if live(u) and u.health() > 0]
            if target not in units:
                units.append(target)
            best = None
            best_value = -1
            for p in (around(position, radius) & mask).positions():
                turn.check()
                hits = [u for u in units if distance(p, u.position()) <= radius]
                value = sum(min(amount, u.health()) for u in hits)
                if distance(p, position) <= radius:
                    value += control
                if value > best_value:
                    best, best_value = p, value
            if best is not None:
                choices.append((best_value, ability, best))
        elif mask.is_set(position):
            choices.append((min(amount, target.health()) + control, ability, target))
    choices.sort(key=lambda row: row[0], reverse=True)
    acted = False
    if choices:
        value, ability, aimed = choices[0]
        if ability.is_attack_reset():
            # Reset after the ordinary attack, including after a ranged walk
            # when an attack allowance has already been consumed.
            acted = attack(target)
            if live(target) and target.health() > 0 and ability.is_ready():
                turn.check()
                if ability.use():
                    acted = True
                    attack(target)
        else:
            turn.check()
            acted = ability.use(aimed)
    if attack(target):
        acted = True
    # An earlier spell may have killed a camp and refreshed Vendetta's reset.
    # One successful cast per turn is still enforced by is_ready/can_cast.
    if me.is_alive() and live(target) and target.health() > 0 and not me.can_attack():
        if me.attack_tiles().is_set(target.position()):
            for ability in me.abilities():
                if ability.is_attack_reset() and ability.is_ready() and turn.may_cast(ability):
                    turn.check()
                    if ability.use():
                        acted = True
                        attack(target)
                    break
    return bool(acted)


def choose_enemy(enemies, allies, defending=False):
    me = bc.me()
    choices = []
    attack_mask = me.attack_tiles()
    for enemy in enemies:
        turn.check()
        gap = distance(me.position(), enemy.position())
        if gap > 7:
            continue
        allied_power = me.health() * max(1, me.strength())
        for ally in allies:
            if ally != me and ally.is_alive() and ally.is_visible() and distance(ally.position(), enemy.position()) <= 5:
                allied_power += ally.health() * max(1, ally.strength()) * 0.75
        enemy_power = sum(e.health() * max(1, e.strength()) for e in enemies
                          if distance(e.position(), enemy.position()) <= 4)
        burst = me.strength() * 2
        for a in me.abilities():
            if a.is_ready() and (a.is_damage() or a.is_cc() or a.is_aoe_damage()):
                burst = max(burst, me.strength() + a.damage_amount(enemy))
        killable = enemy.health() <= burst
        interrupt = enemy.is_submitting_gems() and enemy.gem_count() > 0
        if not (killable or interrupt or defending or gap <= 4 or allied_power > enemy_power * 1.15):
            continue
        # A carrier banks rather than travelling after a healthy enemy.
        if me.gem_count() >= 22 and not (attack_mask.is_set(enemy.position()) and killable):
            continue
        if gap > 4 and not (killable or interrupt or allied_power > enemy_power * 1.15):
            continue
        score = (not attack_mask.is_set(enemy.position()), not interrupt, not killable, enemy.health() / max(1, me.strength()), gap, -enemy.gem_count())
        choices.append((score, enemy))
    return min(choices, key=lambda row: row[0])[1] if choices else None


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
