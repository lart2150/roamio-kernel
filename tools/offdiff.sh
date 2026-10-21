#!/bin/bash
# Whole-kernel struct-offset diff: device image vs our vmlinux (tivo-image tools/mips_align_offset_diff.py).
# Usage: tools/offdiff.sh [tag] [min_funcs]     (after ./vmbuild.sh [tag]) -> build/vm-<tag>/offdiff.md
cd "$(dirname "$0")/.."
. ./env.sh
TAG=${1:-$STBLINUX_TAG}
K=${DEVK:-$HOME/tivo-image/roamio/te4-21.11.1/kernel}
T=${TOOLS:-$HOME/tivo-image/tools}
B=${VMDIR:-build/vm-$TAG}
python3 $T/mips_align_offset_diff.py $K/Image 0x8000ffc0 $K/kallsyms.txt $B/vmlinux $B/System.map ${2:-3} > $B/offdiff.md
sed -n 3p $B/offdiff.md
grep '^## delta' $B/offdiff.md | head -40
