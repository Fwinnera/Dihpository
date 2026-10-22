// Never commit an action from a plan that crossed a fuel suspension.
//
// Ported from the Python turn.py. The engine suspends a bot that exhausts its
// fuel and resumes it inside the same call stack next round, so a decision made
// before the suspension may be acting on a stale view. Measured cost in C++:
// round_number 28 fuel, fuel_remaining 17, so a check is ~45 against a 100,000
// budget -- cheap enough to keep, unlike Python's ~4,694.
#pragma once
#include <cambc.h>
#include <cstdint>
#include <exception>

namespace guard {

struct Replan : std::exception {
    const char* what() const noexcept override { return "replan"; }
};

// Python used 250,000 of 2,500,000 (10%). The same fraction of 100,000.
constexpr std::uint64_t MIN_FUEL = 10000;

inline std::uint32_t started = 0;
inline bool walked = false;

inline void begin() {
    started = cambc::round_number();
    walked = false;
}

inline void check() {
    if (cambc::round_number() != started || cambc::fuel_remaining() < MIN_FUEL)
        throw Replan{};
}

}  // namespace guard
