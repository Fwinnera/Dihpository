"""Visible-target combat. Spell masks give range, not visibility or occupancy."""
import cambc as bc
import config
import turn
from navigation import distance


def live(target):
    turn.check()
    if isinstance(target, bc.Camp):
        # vision.camps() rebuilds the entire SDK camp index; use the known
        # static spawn and a direct, live occupancy query instead.
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
    me = bc.me()
    for ability in me.abilities():
        if not ability.is_heal() or not ability.is_ready() or not turn.may_cast(ability):
            continue
        mask = ability.valid_tiles()
        targets = [ally for ally in allies if ally != me and ally.is_alive()
                   and ally.is_visible() and mask.is_set(ally.position())
                   and ally.max_health() - ally.health() >= config.HEAL_MIN_MISSING]
        if targets:
            target = min(targets, key=lambda c: c.health() / c.max_health())
            turn.check()
            return ability.use(target)
    return False


def fight(target):
    """Damage/control first, then attack, then an unused attack-reset slot."""
    me = bc.me()
    acted = False
    for ability in me.abilities():
        if not ability.is_ready() or not turn.may_cast(ability) or not live(target) or target.health() <= 0:
            continue
        if not (ability.is_damage() or ability.is_aoe_damage() or ability.is_cc()):
            continue
        if not ability.valid_tiles().is_set(target.position()):
            continue
        enemy = isinstance(target, bc.Champion)
        if enemy and not ability.can_target_enemies():
            continue
        if not enemy and not ability.can_target_camps():
            continue
        # Stun immunity removes CC value, but damaging spells can still be useful.
        if enemy and target.champion_name() == bc.ChampionType.MARCELLA:
            if ability.damage_amount(target) <= 0:
                continue
        aimed = target.position() if ability.can_target_ground() else target
        turn.check()
        if ability.use(aimed):
            acted = True
            break

    attacked = attack(target)
    acted |= attacked
    if attacked and live(target) and target.health() > 0 and not me.can_attack():
        for ability in me.abilities():
            if ability.is_attack_reset() and ability.is_ready() and turn.may_cast(ability):
                turn.check()
                if ability.use():
                    acted = True
                    attack(target)
                break
    return acted


def choose_enemy(enemies):
    """No chasing: prefer interruptible tributes, then quick kills and gem carriers."""
    me = bc.me()
    targets = [enemy for enemy in enemies if enemy.is_alive()
               and distance(me.position(), enemy.position()) <= me.attack_range()]
    if not targets:
        return None
    # Cassi/Issac naturally compete on their individual time-to-kill, not a ban
    # on attacking either one. Killing either removes both physical champions.
    return min(targets, key=lambda e: (
        not e.is_submitting_gems(), e.health() / max(1, me.strength()), -e.gem_count()))
