// Deterministic forward model of CAMBC combat, ported from the Python sim.py that
// was validated on 22,029 in-engine predictions. Every constant here was measured
// from engine ground truth, not assumed:
//
//   * a basic attack deals exactly Strength          (ratio 1.000000, n=3532)
//   * Monster emblem multiplies camp damage by 1.1   (1.100000, n=2089)
//   * Durability multiplies incoming damage by 0.9   (uncapped max 0.900000)
//   * Jungle multiplies camp-sourced damage by 0.7   (modal 0.700000, n=857)
//   * the two compose multiplicatively: 0.63         (modal, n=1200)
//   * Heart of Ruin's passive id is 10, not 9        (9 is the retired omnivamp)
//
// Pipeline order, per the SDK's damage_amount contract:
//   base -> outgoing bonuses -> mitigation -> shield absorption -> cap at health
#pragma once
#include <algorithm>
#include <cstdint>

namespace sim {

// PassiveType, confirmed against engine champion designs
enum Passive : int {
    P_NONE = 0,
    P_BONUS_GOLD = 1,            // Vesper Vale
    P_REMOTE_SHOP = 2,           // Tavi
    P_GEM_FOCUS = 3,             // Prism
    P_SPLASH_ATTACK = 4,         // Varg
    P_HEALTH_STRENGTH = 5,       // Ryth
    P_RESET_ON_KILL = 6,         // Vendetta
    P_RETALIATION = 7,           // Ren
    P_STUN_IMMUNITY = 8,         // Marcella
    P_OMNIVAMP_RESERVED = 9,     // retired, id kept reserved by the engine
    P_MISSING_HEALTH_DAMAGE = 10 // Heart of Ruin
};

// ItemPassive, magnitudes as the engine reports them (float32)
enum ItemPassive : int {
    I_NONE = 0, I_MONSTER = 1, I_DURABILITY = 2,
    I_TREASURE = 3, I_JUNGLE = 4, I_HOME = 5
};

constexpr double MAG_MONSTER    = 0.10000000149011612;
constexpr double MAG_DURABILITY = 0.10000000149011612;
constexpr double MAG_TREASURE   = 0.20000000298023224;
constexpr double MAG_JUNGLE     = 0.30000001192092896;
constexpr double MAG_HOME       = 0.5;

constexpr double HOR_MAX_BONUS         = 0.5;
constexpr double REN_RETALIATION_FOCUS = 0.2;
constexpr double RYTH_HEALTH_STRENGTH  = 0.01;
constexpr int    VARG_SPLASH_RADIUS    = 1;

struct Unit {
    double hp = 0.0;
    double max_hp = 0.0;
    double strength = 0.0;
    double focus = 0.0;
    double shield = 0.0;
    int stun = 0;
    int passive = P_NONE;
    bool is_camp = false;
    int attack_range = 1;
    double cdm = 1.0;             // camp_damage_multiplier; 1.0 for every champion seen
    // emblem magnitudes, 0 when the emblem is not held
    double mon = 0.0, dur = 0.0, jun = 0.0;
    int x = 0, y = 0;

    double missing_fraction() const {
        if (max_hp <= 0.0) return 0.0;
        const double f = 1.0 - (hp / max_hp);
        return f < 0.0 ? 0.0 : (f > 1.0 ? 1.0 : f);
    }
};

inline double outgoing_multiplier(const Unit& a, bool target_is_camp) {
    double scale = 1.0;
    if (target_is_camp) {
        scale *= a.cdm;
        if (a.mon != 0.0) scale *= 1.0 + a.mon;
    }
    if (a.passive == P_MISSING_HEALTH_DAMAGE)
        scale *= 1.0 + HOR_MAX_BONUS * a.missing_fraction();
    return scale;
}

inline double incoming_multiplier(const Unit& d, bool source_is_camp) {
    double scale = 1.0;
    if (d.dur != 0.0) scale *= 1.0 - d.dur;
    if (source_is_camp && d.jun != 0.0) scale *= 1.0 - d.jun;
    return scale;
}

inline double basic_attack_base(const Unit& a) { return a.strength; }
inline double ability_base(const Unit& a, double mult) { return mult * a.focus; }

// Health actually lost, through the full pipeline including the health cap.
inline double predict_damage(const Unit& a, const Unit& d, double base) {
    const double raw = base * outgoing_multiplier(a, d.is_camp)
                            * incoming_multiplier(d, a.is_camp);
    const double after = raw - d.shield;
    if (after <= 0.0) return 0.0;
    return after < d.hp ? after : d.hp;
}

// Absorb into shield first, then health. Returns health actually lost.
inline double apply_damage(Unit& d, double raw) {
    double remaining = raw;
    if (d.shield > 0.0) {
        const double absorbed = d.shield < remaining ? d.shield : remaining;
        d.shield -= absorbed;
        remaining -= absorbed;
    }
    if (remaining <= 0.0) return 0.0;
    const double lost = remaining < d.hp ? remaining : d.hp;
    d.hp -= lost;
    return lost;
}

inline double strike(const Unit& a, Unit& d, double base) {
    const double raw = base * outgoing_multiplier(a, d.is_camp)
                            * incoming_multiplier(d, a.is_camp);
    return apply_damage(d, raw);
}

inline double effective_strength(const Unit& c, double bonus_health) {
    if (c.passive == P_HEALTH_STRENGTH)
        return c.strength + RYTH_HEALTH_STRENGTH * bonus_health;
    return c.strength;
}

inline double retaliation_damage(const Unit& d) {
    return d.passive == P_RETALIATION ? REN_RETALIATION_FOCUS * d.focus : 0.0;
}

inline bool in_splash(const Unit& primary, const Unit& other) {
    const int dx = primary.x - other.x, dy = primary.y - other.y;
    const int ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
    return (ax > ay ? ax : ay) <= VARG_SPLASH_RADIUS;
}

}  // namespace sim
