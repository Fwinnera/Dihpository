#!/usr/bin/env python3
"""Identify which build played a match from its per-turn fuel record.

    fuelprint.py PLATFORM_BUNDLE SIDE LOCAL_BUNDLE [LOCAL_BUNDLE ...]

A bundle's team-<side>.fuel is "a62leuf\\0", four bytes, then little-endian
uint64 fuel figures per champion-turn. A team's opening turns depend on its own
code, not the opponent's, so the build whose local run (same map, same side)
starts with the same figures is the one that played.
"""
import struct
import sys
import zipfile


def figures(bundle: str, side: str, n: int = 120) -> list[int]:
    data = zipfile.ZipFile(bundle).read(f"team-{side}.fuel")
    body = data[13:]
    return [struct.unpack_from("<Q", body, 8 * i)[0] for i in range(min(n, len(body) // 8))]


def main() -> None:
    target, side, locals_ = sys.argv[1], sys.argv[2], sys.argv[3:]
    t = figures(target, side)
    for b in locals_:
        f = figures(b, "a")
        same = 0
        for x, y in zip(t, f):
            if x != y:
                break
            same += 1
        print(f"{b.split('/')[-1]:32} matches the first {same} of {min(len(t), len(f))} figures")


if __name__ == "__main__":
    main()
