// turn.py: never commit an action from a plan that crossed a fuel suspension.
#pragma once
#include "common.h"

namespace turn {

struct Replan {};

// Python keeps 250,000 of its 2,500,000. C++ gets a twenty-fifth of Python's fuel,
// so every absolute fuel threshold in this port is the Python one divided by 25.
inline constexpr std::uint64_t FUEL_SCALE = 25;
inline constexpr std::uint64_t MIN_FUEL = 250'000 / FUEL_SCALE;

inline std::int64_t started = -1;
inline bool walked = false;

inline void begin() {
    started = bc::round_number();
    walked = false;
}

inline void check() {
    if (static_cast<std::int64_t>(bc::round_number()) != started || bc::fuel_remaining() < MIN_FUEL)
        throw Replan{};
}

inline bool may_cast(const bc::ability& ability) {
    if (!ability.info()) return false;
    return !(walked && info_exclusive(ability));
}

// A Python threshold, converted.
inline constexpr std::uint64_t fuel(std::uint64_t python) { return python / FUEL_SCALE; }

}  // namespace turn
