// A faithful C++ port of greatsage. Each header mirrors one Python module and keeps
// its decisions, its iteration orders and its tie-breaks, so the two bots can be
// compared game for game. Arithmetic is done in double, as Python does.
#pragma once
#include <cambc.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

namespace bc = cambc;
namespace gm = cambc::map;

inline double D(double x) { return x; }

// Python's `min(items, key=...)`: the first item with the smallest key.
template <class It, class Key>
It first_min(It begin, It end, Key key) {
    It best = end;
    for (It it = begin; it != end; ++it)
        if (best == end || key(*it) < key(*best)) best = it;
    return best;
}

// Fields of the ability's design payload, as Python reads them by attribute name.
inline const std::optional<bc::ability_info>& info_of(const bc::ability& a) { return a.info(); }

inline double info_range(const bc::ability& a) {
    return std::visit([](const auto& v) -> double {
        if constexpr (requires { v.range; }) return v.range; else return 0.0;
    }, a.info().value());
}

// `getattr(ability.info(), 'radius', default)`.
inline double info_radius(const bc::ability& a, double fallback) {
    return std::visit([&](const auto& v) -> double {
        if constexpr (requires { v.radius; }) return v.radius; else return fallback;
    }, a.info().value());
}

inline double info_modifier(const bc::ability& a) {
    return std::visit([](const auto& v) -> double {
        if constexpr (requires { v.modifier; }) return v.modifier; else return 0.0;
    }, a.info().value());
}

inline int info_max_cooldown(const bc::ability& a) {
    return std::visit([](const auto& v) { return v.max_cooldown; }, a.info().value());
}

inline bool info_exclusive(const bc::ability& a) {
    return std::visit([](const auto& v) { return v.exclusive_with_movement; }, a.info().value());
}

inline std::int64_t distance(bc::vec2 a, bc::vec2 b) { return a.chebyshev_distance(b); }

inline std::pair<int, int> key_of(bc::vec2 p) { return {p.x, p.y}; }
