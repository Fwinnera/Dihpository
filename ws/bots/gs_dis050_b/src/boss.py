"""A shielded, healed harvest party for maps gated by a central monolith."""
import cambc as bc
from cambc import game_map as gm
from bot import Bot
import combat
import strategy
import navigation as nav
import turn
from progress import Progress

class BossBot(Bot):
    def __init__(self):
        super().__init__()
        self.bank_progress = Progress()
        self.bank_retry_at = 0

    def bank(self, me, enemies, camps):
        now = bc.round_number()
        if now >= self.bank_retry_at:
            signature = (me.position(), me.gem_count())
            if not self.bank_progress.blocked(signature):
                return super().bank(me, enemies, camps)
            self.bank_retry_at = now + 80
            self.bank_progress.reset()
        # A failed deposit route must not prevent the upgrades needed to open it.
        self.banking = False
        if me.gold_count() >= 30 and self.recall_safe(me, enemies, camps):
            self.team.claim()
            self.objective = None
            turn.check()
            me.recall()
            return
        self.farm(me, enemies)

    def farm(self, me, enemies):
        now, visible = bc.round_number(), bc.vision.visible_tiles()
        nearby = [a for a in self.team.allies if a.is_alive() and a.is_visible()
                  and nav.distance(a.position(), me.position()) <= 6]
        boss_ready = (now >= 650 and self.purchase_index >= 10 and len(nearby) >= 4
                      and sum(a.max_health() for a in nearby) >= 7000
                      and sum(strategy.dps(a, 2) for a in nearby) >= 400)
        claims = self.team.assignments()
        shared = next((claim for a, claim in zip(self.team.allies, claims)
                       if a.is_alive() and claim >= 0), None)
        objective = next((o for o in self.metadata if o.handle == shared
                          and (not o.monolith or now >= 650)
                          and (not boss_ready or o.monolith)), None)
        if objective is not None and not (objective.spawns & visible).is_empty():
            state = objective.group.state()
            if isinstance(state, gm.CampGroupRespawning):
                self.respawns[objective.handle] = now + state.timer
                objective = None
        if objective is None:
            field, reached = nav.field_from(me.position())
            power = sum(a.base_stats().base_strength + a.base_stats().base_focus / 4
                        for a in self.team.allies if a.is_alive())
            best = float('inf')
            for o in self.metadata:
                turn.check()
                if (self.respawns.get(o.handle, 0) > now or (o.monolith and not boss_ready)
                        or (boss_ready and not o.monolith)):
                    continue
                positions = [p for p in o.positions if reached.is_set(p)]
                if not positions:
                    continue
                hp = o.hp
                if not (o.spawns & visible).is_empty():
                    state = o.group.state()
                    if isinstance(state, gm.CampGroupRespawning):
                        self.respawns[o.handle] = now + state.timer
                        continue
                    if isinstance(state, gm.CampGroupRewardAvailable):
                        hp = 0
                score = (min(field.get(p) for p in positions) + hp / max(1, power)
                         + bc.constants.CAPTURE_TIME) / max(1, o.gems + o.gold * 0.4)
                if score < best:
                    objective, best = o, score
                if objective is not None and bc.fuel_remaining() < 700_000:
                    break
        self.objective = objective
        if objective is None:
            self.team.claim()
            if me.gold_count() >= 30 and self.recall_safe(me, enemies, bc.vision.camps()):
                turn.check()
                me.recall()
            return
        self.current_group = objective.handle
        self.team.claim(objective.group)
        targets = combat.visible_camps(objective.camps)
        if not targets:
            self.status('party-travel')
            nav.move_to(objective.spawns)
            return
        target = combat.choose_camp(targets)
        if target is None:
            return
        self.status('party-clear')
        combat.fight(target, targets)
        if combat.live(target) and target.health() > 0:
            if nav.move_to(nav.around(target.position(), me.attack_range())):
                if combat.live(target) and target.health() > 0:
                    combat.fight(target, targets)
        if not any(combat.live(c) and c.health() > 0 for c in targets):
            nav.move_to(objective.spawns)
