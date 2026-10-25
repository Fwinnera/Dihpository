// teamwork.py: six ten-bit task reservations: nine group bits and one support-role bit.
//
// Zero means idle; the low nine bits hold group index + 1 (up to 510).
// Official maps have at most 46 groups. Only collectors reserve the reward;
// supporters reserve their assistance, not a second claim on the same pickup.
#pragma once
#include "common.h"
#include "turn.h"

struct Teamwork {
    std::vector<bc::champion> allies;
    int slot = 0;

    Teamwork() : allies{bc::champions(bc::team::ally)} {
        const auto me = static_cast<std::uint32_t>(static_cast<bc::handle_champion_t>(bc::self()));
        for (std::size_t i = 0; i < allies.size(); ++i)
            if (static_cast<std::uint32_t>(static_cast<bc::handle_champion_t>(allies[i])) == me)
                slot = static_cast<int>(i);
    }

    static std::uint64_t read_word() {
        std::array<std::byte, 8> buffer{};
        bc::shared_memory.read(0, std::span<std::byte>{buffer});
        std::uint64_t word = 0;
        for (int i = 7; i >= 0; --i) word = (word << 8) | static_cast<std::uint64_t>(buffer[i]);
        return word;
    }

    static void write_word(std::uint64_t word) {
        std::array<std::byte, 8> buffer{};
        for (int i = 0; i < 8; ++i) buffer[i] = static_cast<std::byte>((word >> (8 * i)) & 0xFF);
        bc::shared_memory.write(0, std::span<const std::byte>{buffer});
    }

    std::vector<int> assignments() const {
        const auto word = read_word();
        std::vector<int> result;
        for (std::size_t i = 0; i < allies.size(); ++i)
            result.push_back(static_cast<int>((word >> (10 * i)) & 511) - 1);
        return result;
    }

    // `group` is the group handle, or -1 for idle.
    void claim(int group = -1, bool support = false) const {
        std::uint64_t value = group < 0 ? 0 : static_cast<std::uint64_t>(group) + 1;
        if (value > 511) throw std::runtime_error("camp index exceeds reservation capacity");
        if (value && support) value |= 512;
        turn::check();
        auto word = read_word();
        const auto shift = static_cast<std::uint64_t>(slot) * 10;
        word = (word & ~(std::uint64_t{1023} << shift)) | (value << shift);
        turn::check();
        write_word(word);
    }

    std::optional<int> collector(int handle, const bc::bitboard* region = nullptr) const {
        turn::check();
        const auto word = read_word();
        std::vector<int> candidates;
        for (std::size_t i = 0; i < allies.size(); ++i) {
            turn::check();
            const auto value = (word >> (10 * i)) & 1023;
            if (!(value & 512) && static_cast<int>(value & 511) == handle + 1 && allies[i].is_alive())
                candidates.push_back(static_cast<int>(i));
        }
        if (region != nullptr) {
            // A task already being executed is not stolen by a traveller.
            for (int i : candidates) {
                const auto& ally = allies[i];
                if (ally.is_visible()) {
                    const auto position = ally.position();
                    turn::check();
                    if (region->is_set(position)) return i;
                }
            }
        }
        if (candidates.empty()) return std::nullopt;
        return candidates.front();
    }
};

inline int handle_of(const bc::map::camp_group& group) {
    return static_cast<int>(static_cast<std::uint32_t>(static_cast<bc::handle_camp_group_t>(group)));
}

inline std::uint32_t handle_of(const bc::champion& c) {
    return static_cast<std::uint32_t>(static_cast<bc::handle_champion_t>(c));
}

inline std::uint32_t handle_of(const bc::camp& c) {
    return static_cast<std::uint32_t>(static_cast<bc::handle_camp_t>(c));
}

inline bool same(const bc::champion& a, const bc::champion& b) { return handle_of(a) == handle_of(b); }
inline bool same(const bc::camp& a, const bc::camp& b) { return handle_of(a) == handle_of(b); }
