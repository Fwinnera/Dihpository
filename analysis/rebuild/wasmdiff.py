#!/usr/bin/env python3
"""Which compiled functions differ between two bot builds (release wasm).

    wasmdiff.py BOT_A BOT_B          (bot directories under ws/bots, already built)

Disassembles both modules with the wasi-sdk llvm-objdump and compares each function's
instruction sequence by name, with call targets resolved to names. A function counts as
"same" when its opcodes and operands match; "same opcodes" when only immediates differ
(data addresses move when the data segment changes). The engine meters fuel per
instruction, so a function whose opcode sequence is unchanged costs the same fuel for the
same inputs; differing functions are what a change can reach.
"""
import re
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2] / "ws"
OBJ = Path.home() / "Library/Caches/cambc/wasi-sdk-33/bin/llvm-objdump"
HEAD = re.compile(r"^[0-9a-f]+ <(.+)>:$")
INSN = re.compile(r"^\s+[0-9a-f]+:\s+(?:[0-9a-f]{2} )+\s*\t(\S+)\t?(.*)$")


def functions(bot: str):
    wasm = WS / "bots" / bot / ".cambc/build-release/bot.wasm"
    syms = subprocess.run([str(OBJ), "-t", str(wasm)], capture_output=True, text=True).stdout
    imports = []
    for line in syms.splitlines():
        if " F *UND*" in line:
            name = line.split()[-1]
            if name not in imports:
                imports.append(name)
    dis = subprocess.run([str(OBJ), "-d", str(wasm)], capture_output=True, text=True).stdout
    order, body, cur = [], {}, None
    for line in dis.splitlines():
        m = HEAD.match(line)
        if m:
            cur = m.group(1)
            if cur == "CODE":
                cur = None
                continue
            order.append(cur)
            body[cur] = []
            continue
        if cur is None:
            continue
        m = INSN.match(line)
        if m:
            body[cur].append((m.group(1), m.group(2).split('#')[0].strip()))
    n_imp = len(imports)
    out = {}
    for name in order:
        seq = []
        for op, arg in body[name]:
            if op in ("call", "return_call") and arg.isdigit():
                k = int(arg)
                arg = imports[k] if k < n_imp else (order[k - n_imp] if k - n_imp < len(order) else arg)
            seq.append((op, arg))
        out[name] = seq
    return out


def main(a: str, b: str) -> int:
    fa, fb = functions(a), functions(b)
    same = same_ops = 0
    differ, only_a, only_b = [], sorted(set(fa) - set(fb)), sorted(set(fb) - set(fa))
    for name in sorted(set(fa) & set(fb)):
        if fa[name] == fb[name]:
            same += 1
        elif [op for op, _ in fa[name]] == [op for op, _ in fb[name]]:
            same_ops += 1
        else:
            differ.append(name)
    print(f"{a} vs {b}: {len(fa)} / {len(fb)} functions; identical {same}, same opcodes {same_ops}, "
          f"different {len(differ)}, only in {a} {len(only_a)}, only in {b} {len(only_b)}")
    for name in differ:
        print("  differs:", name[:160])
    for name in only_a:
        print(f"  only in {a}:", name[:160])
    for name in only_b:
        print(f"  only in {b}:", name[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
