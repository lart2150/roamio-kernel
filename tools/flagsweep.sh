#!/bin/bash
# Try KCFLAGS variants against the stock modules; one summary line per variant (tools/stockcmp.sh -q).
# Usage: tools/flagsweep.sh 'flags A' 'flags B' ...      (restores the baseline build at the end)
cd "$(dirname "$0")/.."
for f in "" "$@"; do KCFLAGS="$f" tools/stockcmp.sh -q; done
KCFLAGS= tools/stockcmp.sh -q >/dev/null
