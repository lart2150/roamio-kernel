#!/bin/bash
# Disassemble one function by name: device image (kallsyms) or our vmlinux (System.map).
# Usage: tools/dis_fn.sh dev|ours <function>
cd "$(dirname "$0")/.."
. ./env.sh
K=${DEVK:-$HOME/tivo-image/roamio/te4-21.11.1/kernel}
B=${VMDIR:-build/vm-$STBLINUX_TAG}
which=$1; fn=$2
if [ "$which" = dev ]; then MAP=$K/kallsyms.txt; else MAP=$B/System.map; fi
# sed: a 64-bit-BFD nm writes sign-extended ffffffff8... addresses
# stop = the next text symbol at a *higher* address (aliases share the start address); the last
# text symbol has none, so it falls back to start + 0x1000
read a e < <(sed -E 's/^ffffffff//' $MAP | sort | awk -v f="$fn" '
  $2 ~ /^[tTW]$/ { if (hit && $1 != a) {print a, $1; done=1; exit} if (!hit && $3 == f) {a=$1; hit=1} }
  END { if (hit && !done) printf "%s %08x\n", a, strtonum("0x" a) + 0x1000 }')
[ -n "$a" ] || { echo "$fn not in $MAP"; exit 1; }
if [ "$which" = dev ]; then
  mips-linux-gnu-objdump -D -b binary -m mips:isa32 -EL --adjust-vma=0x8000ffc0 \
    --start-address=0x$a --stop-address=0x$e $K/Image | sed -n '/^ *[0-9a-f]*:/p'
else
  mips-linux-gnu-objdump -d --start-address=0x$a --stop-address=0x$e $B/vmlinux | sed -n '/^ *[0-9a-f]*:/p'
fi
