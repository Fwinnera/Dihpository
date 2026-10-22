// Survival model.
//
// Why this exists, from 35 real games across ranks 2-250: our death count is
// roughly constant against every opponent (21, 27, 28, 19, 11 per game) while the
// top two teams die 2.9 times. Dying ~20 times a game is normal for a rank-200
// bot; not dying is the top-team skill and it is the entire gap.
//
// The old Python bot withdrew on a health threshold whose only threat term was
// summed *camp* strength -- enemy champion damage never entered the decision at
// all. This replaces the threshold with an explicit race: how long until we die
// versus how long until we are out of reach. Monsters never chase, so escape is
// always possible if begun early enough; champions do chase, which is why they
// need a different term.
//
// Inputs are parallel flat arrays of doubles. Section 4.3b of the plan measured
// ~1.1 fuel per damage calc on small local arrays against 111.5 on an array of
// fat structs, so the inner loops here never touch a struct.
#pragma once
#include <cstdint>
#include "sim.h"

namespace survive {

constexpr int NO_ESCAPE = 9999;
constexpr double NEVER_DIES = 1.0e9;

// Threat kinds, so mitigation picks the right emblem terms.
enum Kind : int { KIND_CAMP = 0, KIND_CHAMPION = 1 };

// Damage we expect to take next turn, after our own mitigation.
//
// `dist` is Chebyshev distance now; a champion threat is counted as able to close
// one tile per turn, so it reaches us if it is within range + 1.
inline double incoming_per_turn(const sim::Unit& me, int n,
                                const double* strength, const int* range,
                                const int* dist, const int* kind) {
    const double from_camp = (1.0 - me.dur) * (1.0 - me.jun);
    const double from_champ = (1.0 - me.dur);
    double total = 0.0;
    for (int i = 0; i < n; ++i) {
        if (strength[i] <= 0.0) continue;
        const bool camp = kind[i] == KIND_CAMP;
        const int reach = camp ? range[i] : range[i] + 1;
        if (dist[i] > reach) continue;
        total += strength[i] * (camp ? from_camp : from_champ);
    }
    return total;
}

// Turns of damage we can absorb. Shields count: they are health for this purpose.
inline double turns_to_death(const sim::Unit& me, double incoming_per_turn_v) {
    if (incoming_per_turn_v <= 0.0) return NEVER_DIES;
    return (me.hp + me.shield) / incoming_per_turn_v;
}

// Turns to get out of reach of every threat.
//
// A camp at distance d with range r stops reaching us after r - d + 1 steps, and
// never follows. A champion does follow, so walking away does not shed it: only a
// dash opens real distance, and even then only once per cooldown.
inline int turns_to_escape(int n, const int* range, const int* dist,
                           const int* kind, bool has_dash) {
    int worst = 0;
    bool chased = false;
    for (int i = 0; i < n; ++i) {
        const bool camp = kind[i] == KIND_CAMP;
        const int reach = camp ? range[i] : range[i] + 1;
        if (dist[i] > reach) continue;
        if (!camp) { chased = true; continue; }
        const int steps = range[i] - dist[i] + 1;
        if (steps > worst) worst = steps;
    }
    if (chased) {
        // A pursuing champion is only shed by a dash; otherwise assume we cannot.
        if (!has_dash) return NO_ESCAPE;
        if (worst < 2) worst = 2;
    }
    if (worst > 0 && has_dash) worst -= 1;   // a dash covers two tiles in one turn
    return worst < 0 ? 0 : worst;
}

// What to do about the threats, as an action rather than a boolean.
//
// The first version of this returned "disengage" whenever escape was impossible,
// which is exactly backwards: a champion moves at our speed, so walking away from
// one only donates free hits. When a threat cannot be shed the choice is to fight
// or to die, and that is a prediction the simulator can make. Camps never chase,
// so against them withdrawal always works if begun early enough.
//
// `margin` is slack in *turns* -- a quantity with a meaning, unlike a fraction of
// health -- covering a camp waking mid-withdrawal or a second champion arriving.
enum Action : int {
    ACT_CARRY_ON = 0,   // the race is comfortable
    ACT_DISENGAGE = 1,  // losing, and the threats can be shed
    ACT_FIGHT = 2       // losing, and they cannot: standing and fighting is better
};

inline Action decide(double ttd, int tte, double margin) {
    const bool losing = tte >= NO_ESCAPE || ttd <= double(tte) + margin;
    if (!losing) return ACT_CARRY_ON;
    return tte >= NO_ESCAPE ? ACT_FIGHT : ACT_DISENGAGE;
}

// Would we win a straight duel? Turns to kill them against turns to die.
//
// Their emblems are never visible, so their mitigation is unknown and assumed
// absent; their ability output is approximated by a modest uplift on Strength.
inline bool wins_duel(const sim::Unit& me, double my_dps,
                      double their_hp, double their_shield,
                      double their_strength, double their_mitigation_of_us) {
    const double their_dps = their_strength * 1.15 * (1.0 - me.dur);
    if (my_dps <= 0.0) return false;
    const double turns_to_kill = (their_hp + their_shield)
                                 / (my_dps * their_mitigation_of_us);
    if (their_dps <= 0.0) return true;
    const double turns_to_die = (me.hp + me.shield) / their_dps;
    return turns_to_kill < turns_to_die;
}

// Can we survive `turns` more of this? Used to decide whether to finish a camp.
inline bool survives_for(const sim::Unit& me, double incoming_per_turn_v,
                         double turns) {
    if (incoming_per_turn_v <= 0.0) return true;
    return (me.hp + me.shield) > incoming_per_turn_v * turns;
}

// Is casting a shield worth it now, rather than holding it?
//
// A shield absorbs at most its own value, so it pays when enough damage is
// actually coming to consume it. Casting into an empty field wastes the cooldown.
inline bool shield_now(double shield_amount, double incoming_per_turn_v,
                       int horizon_turns, double use_fraction) {
    if (shield_amount <= 0.0 || incoming_per_turn_v <= 0.0) return false;
    return incoming_per_turn_v * double(horizon_turns)
           >= shield_amount * use_fraction;
}

// Our damage per turn against camps: the basic attack plus each usable ability
// amortised over its eight-turn cooldown. Deliberately coarse -- it decides
// whether to commit, not how to fight.
inline double camp_dps(const sim::Unit& me, double basic_per_turn,
                       double ability_per_cycle, double reset_per_cycle) {
    const double out = sim::outgoing_multiplier(me, true);
    return basic_per_turn * out + (ability_per_cycle + reset_per_cycle) * out / 8.0;
}

// Can we clear this group before it kills us?
//
// `incoming_share` is the fraction of the group's combined strength actually
// landing on us over the clear: camps die progressively and some never wake, so
// the full sum overstates it. 0.55 is inherited from the Python bot's tuning.
inline bool can_afford_clear(const sim::Unit& me, double group_health,
                             double group_strength, double dps,
                             double reserve_fraction, double incoming_share,
                             double tolerance) {
    if (dps <= 0.0) return false;
    const double clear_turns = group_health / dps;
    const double from_camp = (1.0 - me.dur) * (1.0 - me.jun);
    const double expected = group_strength * incoming_share * from_camp * clear_turns;
    const double budget = (me.hp + me.shield) - me.max_hp * reserve_fraction;
    // `tolerance` above 1 lets through camps we expect to be pulled off partway.
    // Measured: a strict check (tolerance 1) skipped up to 248 groups per 400
    // turns and cost more income than the deaths it averted. The withdrawal race
    // already handles leaving; this only needs to refuse the hopeless.
    return expected < budget * tolerance;
}

}  // namespace survive
