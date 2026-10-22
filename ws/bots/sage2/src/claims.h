// Task reservations in the team's eight shared bytes.
//
// Ported from the Python teamwork.py. Ten bits per champion: the low nine hold
// group index + 1 (zero means idle), and bit nine marks a supporter rather than
// the collector. Six champions therefore need 60 of the 64 bits, and official
// maps have at most 46 camp groups, so nine bits is enough.
//
// Vision is not shared between champions, so this buffer is the only channel
// there is. Without it every champion ranks the same groups from its own
// position and several converge on the same target.
#pragma once
#include <cambc.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace claims {

constexpr int BITS = 10;
constexpr std::uint64_t GROUP_MASK = 511;   // nine bits
constexpr std::uint64_t SUPPORT_BIT = 512;
constexpr std::uint64_t SLOT_MASK = 1023;
constexpr int MAX_SLOTS = 6;

inline std::uint64_t read_word() {
    std::array<std::byte, 8> bytes{};
    cambc::shared_memory.read(0, bytes);
    std::uint64_t word = 0;
    for (std::size_t i = 0; i < bytes.size(); ++i)
        word |= static_cast<std::uint64_t>(std::to_integer<std::uint8_t>(bytes[i]))
                << (8 * i);
    return word;
}

inline void write_word(std::uint64_t word) {
    std::array<std::byte, 8> bytes{};
    for (std::size_t i = 0; i < bytes.size(); ++i)
        bytes[i] = std::byte{static_cast<std::uint8_t>((word >> (8 * i)) & 0xffu)};
    cambc::shared_memory.write(0, bytes);
}

// Our index among the allied champions, which is our slot in the word.
//
// Cached: the ally list order is fixed for the match, so this answer cannot
// change, and `claim()` is called on nearly every turn by every champion. The
// uncached version made a vector-returning `champions(ally)` call each time --
// a third such call per turn on top of the one in `snapshot()` and the one in
// `escort()`, for data that is identical in all three.
inline int own_slot() {
    static int cached = -1;
    if (cached >= 0) return cached;
    const auto allies = cambc::champions(cambc::team::ally);
    const auto& me = cambc::self();
    cached = 0;
    for (std::size_t i = 0; i < allies.size(); ++i)
        if (allies[i] == me) { cached = static_cast<int>(i); break; }
    return cached;
}

// Group index claimed by each slot, or -1 for idle.
inline void assignments(int* out, int& count, bool* support) {
    const std::uint64_t word = read_word();
    const auto allies = cambc::champions(cambc::team::ally);
    count = static_cast<int>(allies.size());
    if (count > MAX_SLOTS) count = MAX_SLOTS;
    for (int i = 0; i < count; ++i) {
        const std::uint64_t value = (word >> (BITS * i)) & SLOT_MASK;
        out[i] = static_cast<int>(value & GROUP_MASK) - 1;
        support[i] = (value & SUPPORT_BIT) != 0;
    }
}

// Reserve `group_index`, or release with a negative index.
inline void claim(int group_index, bool support = false) {
    std::uint64_t value = 0;
    if (group_index >= 0) {
        if (group_index + 1 > static_cast<int>(GROUP_MASK)) return;  // out of capacity
        value = static_cast<std::uint64_t>(group_index + 1);
        if (support) value |= SUPPORT_BIT;
    }
    const int slot = own_slot();
    std::uint64_t word = read_word();
    const int shift = BITS * slot;
    word = (word & ~(SLOT_MASK << shift)) | (value << shift);
    write_word(word);
}

// A snapshot taken once per turn.
//
// The first version asked `taken_by_other()` per camp group, and each call made
// two vector-returning SDK round-trips (`champions(ally)` twice, via own_slot and
// assignments). Over forty groups that is eighty-odd calls, which exceeded the
// entire 100,000-fuel turn: 3,654 replan throws in one game on a large map, and
// the bot scored nothing. Read the engine once, then answer from arithmetic.
struct Snapshot {
    int slots[MAX_SLOTS]{};
    bool support[MAX_SLOTS]{};
    bool alive[MAX_SLOTS]{};
    int count = 0;
    int mine = 0;

    // Pure arithmetic: no SDK calls, safe to call in a loop.
    bool taken_by_other(int group_index) const {
        if (group_index < 0) return false;
        for (int i = 0; i < count; ++i) {
            if (i == mine || support[i] || !alive[i]) continue;
            if (slots[i] == group_index) return true;
        }
        return false;
    }
};

inline Snapshot snapshot() {
    Snapshot s;
    const std::uint64_t word = read_word();
    const auto allies = cambc::champions(cambc::team::ally);
    const auto& me = cambc::self();
    s.count = static_cast<int>(allies.size());
    if (s.count > MAX_SLOTS) s.count = MAX_SLOTS;
    for (int i = 0; i < s.count; ++i) {
        const std::uint64_t value = (word >> (BITS * i)) & SLOT_MASK;
        s.slots[i] = static_cast<int>(value & GROUP_MASK) - 1;
        s.support[i] = (value & SUPPORT_BIT) != 0;
        s.alive[i] = allies[static_cast<std::size_t>(i)].is_alive();
        if (allies[static_cast<std::size_t>(i)] == me) s.mine = i;
    }
    return s;
}

}  // namespace claims
