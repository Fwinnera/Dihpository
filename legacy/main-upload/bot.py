"""Priority controller. Add experiments in modules; keep a validated snapshot."""
import cambc as bc
from cambc import game_map as gm
import config
import combat
import navigation as nav
import strategy
import turn


class Bot:
    def __init__(self):
        self.groups = None
        self.metadata = None
        self.respawns = {}
        self.current_group = None
        self.purchase_index = 0
        self.last_state = None

    def status(self, label):
        if config.DEBUG and label != self.last_state:
            print(f"STATE r={bc.round_number()} {label} fuel={bc.fuel_remaining()}")
        self.last_state = label

    def shop(self, me):
        build = config.BUILDS.get(me.champion_name(), config.DEFAULT_BUILD)
        # Complete each five-shard emblem before switching families.
        for _ in range(min(40, me.gold_count() // 30)):
            item = build[(self.purchase_index // 5) % len(build)]
            if not me.can_buy(item):
                break
            turn.check()
            me.buy(item)
            self.purchase_index += 1

    def bank(self, me):
        goals = bc.Bitboard()
        locked_goals = bc.Bitboard()
        for altar in gm.altars().positions():
            lock = bc.vision.altar_lock_at(altar) if bc.vision.has_altar_lock(altar) else None
            if lock is not None and lock.is_enemy():
                if nav.distance(me.position(), altar) <= me.attack_range() and me.can_attack():
                    turn.check()
                    me.attack(lock)
                    return
                locked_goals |= nav.around(altar, bc.constants.SUBMIT_GEMS_RANGE)
                continue
            if nav.distance(me.position(), altar) <= bc.constants.SUBMIT_GEMS_RANGE:
                turn.check()
                me.submit_gems(altar)
                return
            goals |= nav.around(altar, bc.constants.SUBMIT_GEMS_RANGE)
        if not nav.move_to(goals):
            nav.move_to(locked_goals)

    def farm(self, me):
        group = strategy.choose_group(self.metadata, me, self.respawns, self.current_group)
        if group is None:
            if me.gem_count():
                self.bank(me)
            return
        self.current_group = group.__index__()
        visible = bc.vision.visible_tiles()
        seen = not (group.spawn_tiles() & visible).is_empty()
        if seen and isinstance(group.state(), gm.CampGroupRewardAvailable):
            self.status("capture")
            nav.move_to(group.spawn_tiles())
            return
        self.status("farm")
        targets = [c for c in group.camps() if c.is_visible() and c.health() > 0]
        if targets:
            target = min(targets, key=lambda c: (
                nav.distance(me.position(), c.position()) > me.attack_range(), c.health()))
            combat.fight(target)
            if combat.live(target) and target.health() > 0:
                moved = nav.move_to(nav.around(target.position(), me.attack_range()))
                # WHY: preserve an in-range spell before approaching, rather than
                # sacrificing it to walk first. If a melee walk succeeds, use the
                # remaining legal attack/reset opportunities immediately.
                if moved and me.base_stats().base_attack_range <= 1:
                    turn.check()
                    if combat.live(target) and target.health() > 0:
                        combat.fight(target)
        else:
            nav.move_to(group.spawn_tiles())

    def play_turn(self):
        me = bc.me()
        if self.groups is None:
            self.groups = gm.camp_groups()
            me.set_priority(config.PRIORITY.get(me.champion_name(), 10))
        if self.metadata is None:
            self.metadata = strategy.prepare(self.groups)
        self.shop(me)  # Shopping is allowed while dead, too.
        if not me.is_alive():
            self.status("dead")
            return
        if me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            self.status("channel")
            return
        if not (me.can_move() or me.can_attack() or me.can_cast()):
            self.status("disabled")
            return
        at_spawn = gm.spawn_region(bc.Team.ALLY).is_set(me.position())
        if at_spawn and me.health() < me.max_health():
            self.status("heal-at-spawn")
            return
        enemies = [e for e in bc.vision.champions(bc.Team.ENEMY) if e.is_alive()]
        camp_tiles = bc.vision.camp_tiles()
        camps = [c for group in self.groups for c in group.camps()
                 if camp_tiles.is_set(c.spawn_position())]
        turn.check()
        allies = bc.champions(bc.Team.ALLY)
        turn.check()
        combat.heal_allies(allies)
        threshold = config.CARRIER_RETREAT_HEALTH if me.gem_count() else config.RETREAT_HEALTH
        if not at_spawn and me.health() < me.max_health() * threshold:
            self.status("retreat")
            enemy_safe = all(nav.distance(me.position(), e.position()) > config.ENEMY_RECALL_CLEARANCE
                             for e in enemies)
            camp_safe = all(c.strength() <= 0 or nav.distance(me.position(), c.position()) > c.attack_range()
                            for c in camps)
            if enemy_safe and camp_safe:
                turn.check()
                me.recall()
            else:
                nav.retreat(enemies, camps)
            return
        # Enemy spawn recovery can sustain a target indefinitely. Keep those
        # enemies in the retreat threat list, but do not farm fights at spawn.
        enemy_spawn = gm.spawn_region(bc.Team.ENEMY)
        pursuit_enemies = [e for e in enemies if not enemy_spawn.is_set(e.position())]
        if pursuit_enemies:
            target = min(pursuit_enemies, key=lambda e: nav.distance(me.position(), e.position()))
            if nav.distance(me.position(), target.position()) <= 7:
                combat.fight(target)
                if combat.live(target) and me.can_move():
                    nav.move_to(nav.around(target.position(), me.attack_range()))
                    turn.check()
                    combat.attack(target)
                return
        # Near-complete captures precede new trips to the altar.
        visible = bc.vision.visible_tiles()
        for group in self.groups:
            if group.spawn_tiles().is_set(me.position()):
                if (not (group.spawn_tiles() & visible).is_empty()
                        and isinstance(group.state(), gm.CampGroupRewardAvailable)):
                    self.status("capture")
                    return
        if strategy.should_bank(enemies):
            self.status("bank")
            self.bank(me)
            return
        target = combat.choose_enemy(pursuit_enemies)
        if target is not None:
            self.status("combat")
            combat.fight(target)
            return
        self.farm(me)
