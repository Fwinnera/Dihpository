#!/bin/bash
m=$1; out=$2
mkdir -p "$out/$m"
cd /Users/faeezaullyar/Claude/battlecode/ws && cambc run --release --rounds 6 --map "$m" -o "$out/$m" bots/p_hjt bots/p_hjt >/dev/null 2>&1
