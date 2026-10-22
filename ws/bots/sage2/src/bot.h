#pragma once
#include <cambc.h>
#include "sim.h"
#include <array>
#include <cstdint>
#include <optional>
#include <cstddef>
#include <vector>

class Bot {
public:
    void play_turn();

private:
    void shop();
    bool survive_check();
    bool heal_trip();
    bool withdraw(const std::vector<cambc::champion>& enemies,
                  const std::vector<cambc::camp>& live_camps, double ttd);
    bool bank();
    bool farm();
    bool boss_farm();

    // Group geometry and design values never change, so they are read from the
    // engine exactly once. The selection loop then touches no SDK call at all:
    // `spawn_tiles()` plus `.positions()` per group was costing 4,851 replan
    // throws a game on a large map.
    struct GroupInfo {
        int handle = -1;
        std::size_t index = 0;
        std::vector<cambc::vec2> tiles;
        std::uint32_t value = 0;
        // Static facts boss mode scores on. A camp's kind() needs no vision and
        // base_stats() is a per-kind design lookup, so both are free after the
        // first of each kind.
        // The group's spawn-tile mask, built once. `spawn_tiles()` is not a read:
        // it clears a bitboard and then calls `sdk_Bitboard_Set` once per camp,
        // so asking for it every turn was paying N+1 engine calls a turn for a
        // mask that cannot change.
        std::optional<cambc::bitboard> mask;
        bool monolith = false;
        double hp = 0.0;
        std::uint32_t gems = 0, gold = 0;
    };

    std::optional<std::vector<cambc::map::camp_group>> groups_;
    std::vector<GroupInfo> info_;
    int purchase_index_ = 0;
    int target_handle_ = -1;        // claim id of the group we are committed to

    // Stall guard, ported from the Python Progress class: a target that stops
    // changing anything is unreachable, so drop it and try elsewhere.
    cambc::vec2 stall_pos_{};
    double stall_health_ = -1.0;
    int stall_ticks_ = 0;
    std::array<std::int32_t, 64> blocked_until_{};

    // Banking stall guard, boss maps only. Ported from boss.py's use of Progress:
    // on a map whose only altar is gated, a carrier will route toward it forever
    // and never fight the thing that opens it. Twelve turns with the position and
    // the bag both unchanged means there is no route; stop trying for eighty
    // rounds and go and earn the upgrades instead.
    cambc::vec2 bank_sig_pos_{};
    std::uint32_t bank_sig_gems_ = 0xffffffffu;
    int bank_stall_ = 0;
    std::int32_t bank_retry_at_ = 0;
    bool bank_allowed();

    const cambc::map::camp_group* group_by_handle(int handle) const;
    const cambc::bitboard& group_mask(const cambc::map::camp_group& g);
    // One definition of what a group costs, kept from the escort's gate: the
    // selection loop and anything else that ranks a group score it the same way.
    std::int32_t group_cost(cambc::vec2 pos, const GroupInfo& gi,
                            const std::vector<cambc::vec2>& enemies,
                            double dps) const;

    bool target_still_good(const cambc::map::camp_group& g);
    double camp_dps(const sim::Unit& u) const;
    void load_groups();
    // Altars never move, so their positions and the ring of tiles that can
    // tribute at them are read from the engine once.
    void load_altars();
    std::vector<cambc::vec2> altars_;
    cambc::bitboard altar_goals_;
    bool altars_loaded_ = false;
};
