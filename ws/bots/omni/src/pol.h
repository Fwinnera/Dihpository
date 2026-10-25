// Per map-side policy. Every behaviour below was a separate bot measured on all 80
// map-sides against gs_src2_c1_eqsoft; omni carries them all as switches and picks
// one per map and side from policy_table.h (maps are told apart by width, height,
// camp groups and total gems, which differ on all 40 maps; the side is the team id).
#pragma once
#include "common.h"

namespace pol {

struct Policy {
    int build = 0;            // index into builds(): 0 Treasure>Bruiser>Durability
    int assist_range = 0;     // join a teammate's fight within this range; 0 off
    int assist_until = 100000;
    int ally_range = 0;       // retreat toward a healthy teammate within this range; 0 off
    bool stay_beside = false;
    int squad_rounds = 0;     // early followers take their leader's camp; 0 off
    int cohesion_until = 0;   // prefer camps near a teammate before this round; 0 off
    int cohesion_weight = 4;
    int shop_gold = 150;
    int shop_interval = 70;
    int draft = 0;            // 0 default, 1 Tavi fourth, 2 Tavi fifth, 3 Cassi fifth
    bool stand = true;        // fight back when caught while disengaging
    bool cheap_reject = false; // skip the tile scan for unseen groups the damage test rejects
    bool coop = true;         // fall back to the cooperative rally when no group suits
    int rows_fuel = 950'000;  // choose_group stops scoring rows below this (Python units)
    double retreat = 0.30;    // retreat below this health fraction (carrying gems: carrier)
    double carrier = 0.43;
    double disengage = 0.5;   // leave a fight below this local strength ratio
    int bank_gems = 24;
    double heal_recall = 0.60;
    bool party_off = false;   // play party maps with the solo controller
};

// The measured arms, by the bench name they were measured as.
inline const std::vector<Policy>& arms() {
    static const std::vector<Policy> table = [] {
        std::vector<Policy> t;
        auto add = [&](Policy p) { t.push_back(p); return t.size() - 1; };
        Policy base;                                    // 0 b_tbd
        add(base);
        Policy p = base; p.build = 1; add(p);           // 1 m_stand
        p = base; p.build = 2; add(p);                  // 2 b_jtd
        p = base; p.build = 3; add(p);                  // 3 b_btd
        p = base; p.build = 4; add(p);                  // 4 b_dtj
        p = base; p.build = 5; add(p);                  // 5 b_jbd
        p = base; p.assist_range = 10; add(p);          // 6 as10
        p = base; p.assist_range = 10; p.assist_until = 600; add(p);  // 7 as10e
        p = base; p.assist_range = 14; add(p);          // 8 as14
        p = base; p.build = 1; p.ally_range = 8; add(p);              // 9 r_ally
        p = base; p.build = 1; p.ally_range = 12; add(p);             // 10 r_ally12
        p = base; p.build = 1; p.ally_range = 8; p.stay_beside = true; add(p);  // 11 r_stay
        p = base; p.ally_range = 8; add(p);             // 12 b_tbd_ally
        p = base; p.squad_rounds = 300; add(p);         // 13 sq_base
        p = base; p.squad_rounds = 200; add(p);         // 14 sq_200
        p = base; p.squad_rounds = 500; add(p);         // 15 sq_500
        p = base; p.squad_rounds = 100000; add(p);      // 16 sq_all
        p = base; p.build = 1; p.cohesion_until = 400; add(p);        // 17 c_e4
        p = base; p.build = 1; p.cohesion_until = 100000; p.cohesion_weight = 2; add(p);  // 18 c_all2
        p = base; p.build = 1; p.cohesion_until = 400; p.cohesion_weight = 2; add(p);     // 19 c_e2
        p = base; p.build = 1; p.shop_gold = 120; add(p);             // 20 sh120
        p = base; p.build = 1; p.shop_interval = 40; add(p);          // 21 shi40
        p = base; p.build = 1; p.draft = 1; add(p);     // 22 dr_tavi4
        p = base; p.build = 1; p.draft = 2; add(p);     // 23 dr_tavi5
        p = base; p.build = 1; p.draft = 3; add(p);     // 24 dr_cassi5
        p = base; p.build = 1; p.stand = false; add(p); // 25 gs_merge
        p = base; p.cheap_reject = true; add(p);        // 26 b_sf
        p = base; p.build = 1; p.cheap_reject = true; add(p);  // 27 m_stand + stall fix
        p = base; p.coop = false; add(p);               // 28 w_nocoop
        p = base; p.build = 1; p.assist_range = 10; add(p);    // 29 Jungle + assist
        p = base; p.build = 1; p.squad_rounds = 300; add(p);   // 30 Jungle + squads
        p = base; p.rows_fuel = 1'900'000; add(p);      // 31 w_rows75
        p = base; p.retreat = 0.20; p.carrier = 0.33; add(p);  // 32 retreat later
        p = base; p.retreat = 0.40; p.carrier = 0.53; add(p);  // 33 retreat earlier
        p = base; p.disengage = 0.35; add(p);           // 34 leave fights later
        p = base; p.disengage = 0.70; add(p);           // 35 leave fights earlier
        p = base; p.bank_gems = 16; add(p);             // 36 bank small bags
        p = base; p.bank_gems = 34; add(p);             // 37 bank big bags
        p = base; p.heal_recall = 0.45; add(p);         // 38 heal later
        p = base; p.heal_recall = 0.75; add(p);         // 39 heal earlier
        p = base; p.party_off = true; add(p);           // 40 no party controller
        p = base; p.build = 1; p.party_off = true; add(p);     // 41 Jungle, no party controller
        return t;
    }();
    return table;
}

}  // namespace pol
