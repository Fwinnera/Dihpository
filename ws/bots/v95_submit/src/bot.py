"""Score first: survive, bank, defend captures, then clear assigned camps."""
import cambc as bc
from cambc import game_map as gm
import config
import combat
import navigation as nav
import strategy
import teamwork
import turn
from progress import Progress

class Bot:
    def __init__(self):
        self.groups = None
        self.metadata = None
        self.respawns = {}
        self.current_group = None
        self.objective = None
        self.purchase_index = 0
        self.scaling_item = None
        self.last_purchase = -100
        self.banking = False
        self.disengaging = False
        self.team = None
        self.altar_field = None
        self.last_state = None
        self.mobility_mode = None
        self.by_tile = {}
        self.progress = Progress()
        self.supporting_handle = None
        self.bank_progress = Progress(limit=10)

    def status(self, label):
        if config.DEBUG and label != self.last_state:
            print(f'STATE r={bc.round_number()} {label} fuel={bc.fuel_remaining()}')
        self.last_state = label

    def shop(self, me):
        # Buy the route-enabling tool before shards drain the purse. A dash
        # cannot land on a monster blocking a narrow island entrance.
        if nav.needs_crystal() and me.can_buy(bc.ConsumableType.TP_CRYSTAL):
            turn.check()
            me.buy(bc.ConsumableType.TP_CRYSTAL)
        if me.can_buy(bc.ConsumableType.ALTAR_LOCK):
            turn.check()
            me.buy(bc.ConsumableType.ALTAR_LOCK)
        build = config.BUILDS.get(me.champion_name(), config.DEFAULT_BUILD)
        for _ in range(min(40, me.gold_count() // 30)):
            emblem = self.purchase_index // 5
            if emblem < len(build):
                item = build[emblem]
            else:
                # Finish the current emblem before comparing the next purchase.
                # Maximise the marginal health x damage product using live stats.
                if self.scaling_item is None or self.purchase_index % 5 == 0:
                    stats = me.base_stats()
                    health_gain = stats.health_growth * me.strength()
                    damage_gain = stats.strength_growth * me.max_health()
                    self.scaling_item = (bc.ItemType.POWER_SHARD_OF_HEALTH
                                         if health_gain > damage_gain
                                         else bc.ItemType.POWER_SHARD_OF_STRENGTH)
                item = self.scaling_item
            if not me.can_buy(item):
                break
            # Batch the remainder of this emblem; this also reduces SDK/fuel
            # overhead on a rich respawn without skipping any shard purchases.
            count = min(5 - self.purchase_index % 5, me.gold_count() // 30)
            turn.check()
            me.buy(item, count)
            self.purchase_index += count
            self.last_purchase = bc.round_number()
        if nav.needs_crystal() and me.can_buy(bc.ConsumableType.TP_CRYSTAL):
            turn.check()
            me.buy(bc.ConsumableType.TP_CRYSTAL)

    def recall_safe(self, me, enemies, camps):
        return (all(nav.distance(me.position(), e.position()) > 6 for e in enemies)
                and all(not c.is_awake() or c.strength() <= 0
                        or nav.distance(me.position(), c.position()) > c.attack_range() for c in camps))

    def bank(self, me, enemies, camps):
        self.team.claim()
        if self.bank_progress.blocked((me.position(), me.gem_count())):
            if self.recall_safe(me, enemies, camps):
                turn.check()
                me.recall()
                self.bank_progress.reset()
                return
        goals, locked = bc.Bitboard(), bc.Bitboard()
        for altar in gm.altars().positions():
            turn.check()
            lock = bc.vision.altar_lock_at(altar) if bc.vision.has_altar_lock(altar) else None
            if lock is not None and lock.is_enemy():
                if me.can_attack() and me.attack_tiles().is_set(altar):
                    turn.check()
                    me.attack(lock)
                    return
                locked |= nav.around(altar, bc.constants.SUBMIT_GEMS_RANGE)
            else:
                if nav.distance(me.position(), altar) <= bc.constants.SUBMIT_GEMS_RANGE:
                    turn.check()
                    me.submit_gems(altar)
                    return
                goals |= nav.around(altar, bc.constants.SUBMIT_GEMS_RANGE)
        if not goals.is_empty():
            if nav.move_to(goals, nav.threat_mask(enemies, camps)):
                return
            if nav.move_to(goals):
                return
        nav.move_to(locked)

    def farm(self, me, enemies):
        objective = self.objective
        if objective is not None:
            if not (objective.spawns & bc.vision.visible_tiles()).is_empty():
                state = objective.group.state()
                if isinstance(state, gm.CampGroupRespawning):
                    self.respawns[objective.handle] = bc.round_number() + state.timer
                    objective = None
                elif isinstance(state, gm.CampGroupRewardAvailable):
                    owner = self.team.collector(objective.handle, objective.spawns)
                    if owner is not None and owner != self.team.slot:
                        objective = None
        if objective is None:
            self.supporting_handle = None
            objective = strategy.choose_group(self.metadata, me, self.respawns,
                                              self.current_group, self.team, enemies)
        if objective is None:
            objective = strategy.choose_cooperative(self.metadata, me, self.respawns, self.team)
            if objective is not None and self.team.collector(objective.handle, objective.spawns) is not None:
                self.supporting_handle = objective.handle
        self.objective = objective
        if objective is None:
            self.team.claim()
            if me.gem_count():
                self.banking = True
                self.bank(me, enemies, [])
            elif self.by_tile.get(me.position()) is not None:
                occupied = bc.Bitboard()
                for o in self.metadata:
                    occupied |= o.spawns
                nav.park_nearby(occupied)
            elif me.gold_count() >= 150 and self.recall_safe(me, enemies, []):
                turn.check()
                me.recall()
            return
        self.current_group = objective.handle
        self.team.claim(objective.group, support=self.supporting_handle == objective.handle)
        # Static routing deliberately ignores unknown camp occupancy. Detect
        # a blocked landing or choke rather than retrying it for 2,000 turns.
        # Record before the expensive planner so fuel suspension cannot skip
        # recovery. Damage and movement both count as measurable progress.
        observed = combat.visible_camps(objective.camps)
        health = []
        for camp in observed:
            turn.check()
            health.append((camp.__index__(), camp.health()))
        signature = (objective.handle, me.position(), tuple(health))
        if self.progress.blocked(signature):
            self.respawns[objective.handle] = bc.round_number() + 80
            self.objective = None
            self.current_group = None
            self.team.claim()
            self.progress.reset()
            return
        group = objective.group
        visible = bc.vision.visible_tiles()
        if not (objective.spawns & visible).is_empty():
            state = group.state()
            if isinstance(state, gm.CampGroupRewardAvailable):
                self.status('capture')
                nav.move_to(objective.spawns)
                return
        targets = observed
        if not targets:
            nav.move_to(objective.spawns)
            return
        target = combat.choose_camp(targets)
        if target is None:
            return
        self.status('farm')
        combat.fight(target, targets)
        # A spell or kill-reset can leave an ordinary attack unused. Immediately
        # switch to the next living monster instead of wasting the allowance.
        for _ in range(3):
            if combat.live(target) or not (me.can_attack() or me.can_cast()):
                break
            remaining = [c for c in targets if combat.live(c) and c.health() > 0]
            if not remaining:
                break
            target = min(remaining, key=lambda c: (
                not me.attack_tiles().is_set(c.position()), c.health()))
            combat.fight(target, targets)
        if combat.live(target) and target.health() > 0:
            if nav.move_to(nav.around(target.position(), me.attack_range())):
                if combat.live(target) and target.health() > 0:
                    combat.fight(target, targets)
        # When the last monster falls, start travelling onto the reward now.
        if not combat.live(target):
            remaining = [c for c in targets if combat.live(c) and c.health() > 0]
            if not remaining:
                nav.move_to(objective.spawns)

    def reserve_capture(self, holding):
        """Keep an executing collector; helpers step away only after handover."""
        owner = self.team.collector(holding.handle, holding.spawns)
        assisting = owner is not None and owner != self.team.slot
        self.team.claim(holding.group, support=assisting)
        if assisting:
            collector = self.team.allies[owner]
            if collector.is_visible() and holding.spawns.is_set(collector.position()):
                nav.move_to(nav.around(collector.position(),4) & ~holding.spawns, use_dash=False)
                return True
        return False

    def play_turn(self):
        me = bc.me()
        if self.groups is None:
            self.groups = gm.camp_groups()
            self.team = teamwork.Teamwork()
            turn.check()
            me.set_priority(config.PRIORITY.get(me.champion_name(), 10))
        self.shop(me)
        if not me.is_alive():
            self.team.claim()
            self.current_group = None
            self.objective = None
            self.status('dead')
            return
        if me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            held = self.by_tile.get(me.position())
            if held is not None and isinstance(held.group.state(), gm.CampGroupRewardAvailable):
                owner = self.team.collector(held.handle, held.spawns)
                self.team.claim(held.group, support=owner is not None and owner != self.team.slot)
            else:
                self.team.claim()
            return
        if not (me.can_move() or me.can_attack() or me.can_cast()):
            return
        mode = nav.mobility()
        if self.metadata is None or self.mobility_mode != mode:
            self.metadata = strategy.prepare(self.groups)
            self.mobility_mode = mode
            self.by_tile = {p: o for o in self.metadata for p in o.positions}
        if self.altar_field is None:
            goals = bc.Bitboard()
            for altar in gm.altars().positions():
                goals |= nav.around(altar, bc.constants.SUBMIT_GEMS_RANGE)
            self.altar_field = bc.DistanceField()
            self.altar_field.compute(nav.static_walls(), goals & ~nav.static_walls(), bc.Bitboard())
        turn.check()
        at_spawn = gm.spawn_region(bc.Team.ALLY).is_set(me.position())
        if at_spawn and me.health() < me.max_health():
            self.team.claim()
            return
        enemies = [e for e in bc.vision.champions(bc.Team.ENEMY) if e.is_alive()]
        camps = bc.vision.camps()
        turn.check()
        combat.heal_allies(self.team.allies)
        threshold = config.CARRIER_RETREAT_HEALTH if me.gem_count() else config.RETREAT_HEALTH
        position = me.position()
        camp_pressure = sum(c.strength() for c in camps if c.is_awake()
                            and nav.distance(position, c.position()) <= c.attack_range())
        # Monsters act before our next turn. Leave enough health for the two
        # attacks a melee champion may take while walking out of a dense pack.
        retreat_at = max(me.max_health() * threshold, camp_pressure * 2 + me.max_health() * 0.08)
        if not at_spawn and me.health() < retreat_at:
            self.status('retreat')
            self.objective = None
            self.team.claim()
            if self.recall_safe(me, enemies, camps):
                turn.check()
                me.recall()
            else:
                # Damage/reset before withdrawing can kill a pursuer. Ranged
                # champions must preserve their ordinary move allowance.
                if me.base_stats().base_attack_range <= 1:
                    close = [e for e in enemies if nav.distance(me.position(), e.position()) <= 1]
                    if close:
                        combat.fight(min(close, key=lambda e: e.health()), close)
                nav.retreat(enemies, camps)
            return
        ratio, threats = combat.local_power(enemies, self.team.allies, config.DISENGAGE_RADIUS)
        leave = config.DISENGAGE_RATIO + (config.DISENGAGE_HYSTERESIS if self.disengaging else 0)
        self.disengaging = not at_spawn and threats > 0 and ratio < leave
        if self.disengaging:
            self.status('disengage')
            self.objective = None
            self.team.claim()
            # Take a kill that is already in reach before leaving: it removes a
            # threat and pays gold. Only melee champions can, as in the low-health
            # retreat: a ranged champion moves or attacks in a turn, not both, so
            # the swing would cost it the escape step. (Builds before this change
            # -- gs_dis050, gs_dis075, the _out and _b variants -- swung at any range.)
            target = combat.finishing_blow(enemies) if me.base_stats().base_attack_range <= 1 else None
            if target is not None:
                combat.fight(target, enemies)
            nav.retreat(enemies, camps)
            return
        holding = self.by_tile.get(me.position())
        if holding is not None and not isinstance(holding.group.state(), gm.CampGroupRewardAvailable):
            holding = None
        if holding is not None:
            self.current_group = holding.handle
            if self.reserve_capture(holding):
                return
            self.status('capture')
            if me.gem_count():
                for altar in gm.altars().positions():
                    if nav.distance(me.position(), altar) <= bc.constants.SUBMIT_GEMS_RANGE:
                        if not bc.vision.has_altar_lock(altar) or not bc.vision.altar_lock_at(altar).is_enemy():
                            turn.check()
                            me.submit_gems(altar)
                            return
            target = combat.choose_enemy(enemies, self.team.allies, defending=True)
            if target is not None:
                combat.fight(target, enemies)
            return
        if not me.gem_count():
            self.banking = False
            self.bank_progress.reset()
        if self.banking or strategy.should_bank(enemies, self.altar_field.get(me.position())):
            self.banking = True
            self.status('bank')
            self.objective = None
            self.bank(me, enemies, camps)
            return
        if (not at_spawn and me.gold_count() >= config.SHOP_GOLD
                and bc.round_number() - self.last_purchase >= config.SHOP_INTERVAL
                and bc.round_number() < bc.constants.MAX_ROUNDS - 150
                and self.recall_safe(me, enemies, camps)):
            self.team.claim()
            self.objective = None
            turn.check()
            me.recall()
            return
        enemy_spawn = gm.spawn_region(bc.Team.ENEMY)
        pursuit = [e for e in enemies if not enemy_spawn.is_set(e.position())]
        target = combat.choose_enemy(pursuit, self.team.allies)
        if target is not None:
            self.status('combat')
            acted = combat.fight(target, pursuit)
            moved = False
            if combat.live(target) and target.health() > 0:
                moved = nav.move_to(nav.around(target.position(), me.attack_range()))
                if moved and combat.live(target) and target.health() > 0:
                    acted = combat.fight(target, pursuit) or acted
            if acted or moved:
                return
        self.farm(me, enemies)
