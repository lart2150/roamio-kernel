#!/bin/bash
# Device kallsyms vs our vmlinux: score + per-CONFIG attribution (tivo-image tools/sym_diff.py).
# Usage: tools/symdiff.sh [tag] [out.md]     (after ./vmbuild.sh [tag])
cd "$(dirname "$0")/.."
. ./env.sh
TAG=${1:-$STBLINUX_TAG}
OUT=${2:-$HOME/tivo-image/roamio/kernel-sym-diff.md}
DEVKS=${DEVKS:-$HOME/tivo-image/roamio/te4-21.11.1/kernel/kallsyms.txt}
T=${TOOLS:-$HOME/tivo-image/tools}
B=${VMDIR:-build/vm-$TAG}
python3 $T/roamio_symscore.py $DEVKS $B/System.map
(cd $B && python3 $T/sym_diff.py $DEVKS System.map . .config "$OUT" >/dev/null 2>&1)
grep -E '^## |^\| `' "$OUT" | awk -F'|' '/^## /{print; next} {printf "%-42s %-30s %5s %s\n", $2, $3, $4, substr($5,1,110)}'
