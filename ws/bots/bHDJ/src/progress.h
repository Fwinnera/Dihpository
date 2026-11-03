// progress.py: recover from an impassable objective without confusing attacks with idling.
#pragma once
#include "common.h"

struct Progress {
    int limit;
    std::optional<std::vector<double>> signature;
    int ticks = 0;

    explicit Progress(int limit = 12) : limit{limit} {}

    void reset() {
        signature.reset();
        ticks = 0;
    }

    bool blocked(const std::vector<double>& next) {
        if (signature && *signature == next) {
            ++ticks;
        } else {
            signature = next;
            ticks = 0;
        }
        return ticks >= limit;
    }
};
