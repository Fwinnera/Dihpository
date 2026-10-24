"""Keep Willow in healing range of a productive front-line farmer."""
import cambc as bc
from cambc import game_map as gm
from bot import Bot
import navigation as nav
import combat
import turn

class EscortBot(Bot):
    reach = 3

    def farm(self, me, enemies):
        claims = self.team.assignments()
        candidates = []
        for index, ally in enumerate(self.team.allies):
            turn.check()
            if ally == me or not ally.is_alive() or claims[index] < 0:
                continue
            objective = next((o for o in self.metadata if o.handle == claims[index]), None)
            if objective is None:
                continue
            priority = 0 if ally.champion_name() == bc.ChampionType.VARG else 1
            if ally.is_visible():
                priority += nav.distance(me.position(), ally.position()) / 12
                if ally.health() < ally.max_health() * 0.7:
                    priority -= 1
            candidates.append((priority, index, ally, objective))
        if not candidates:
            return super().farm(me, enemies)
        _, _, leader, objective = min(candidates, key=lambda row: (row[0], row[1]))
        self.objective = objective
        self.current_group = objective.handle
        self.team.claim(objective.group, support=True)
        visible = bc.vision.visible_tiles()
        if not (objective.spawns & visible).is_empty():
            state = objective.group.state()
            if isinstance(state, gm.CampGroupRespawning):
                self.respawns[objective.handle] = bc.round_number() + state.timer
                self.team.claim()
                self.objective = None
                return super().farm(me, enemies)
        targets = combat.visible_camps(objective.camps)
        if targets:
            target = min(targets, key=lambda c: (not me.attack_tiles().is_set(c.position()), c.health()))
            combat.fight(target, targets)
            if combat.live(target) and target.health() > 0:
                nav.move_to(nav.around(target.position(), self.reach if leader.is_visible() else 1))
        else:
            anchor = leader.position() if leader.is_visible() else objective.positions[0]
            nav.move_to(nav.around(anchor, self.reach if leader.is_visible() else 1) & ~objective.spawns)
        combat.heal_allies(self.team.allies)


class TankBot(EscortBot):
    """Heart of Ruin: follow a teammate to its camp and fight adjacent to the target."""
    reach = 1
