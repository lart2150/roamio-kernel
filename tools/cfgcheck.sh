#!/bin/bash
# Report fragment lines that did not survive oldconfig (dependency not met / symbol unknown).
# Usage: tools/cfgcheck.sh <.config> [fragment]
CFG=${1:?usage: cfgcheck.sh <.config> [fragment]}
FRAG=${2:-$(dirname "$0")/../config/roamio_fragment.config}
grep -E '^(CONFIG_[A-Z0-9_]+=|# CONFIG_[A-Z0-9_]+ is not set)' "$FRAG" | while read -r l; do
  if [[ $l == "# "* ]]; then s=${l#\# }; s=${s% is not set}
    grep -qE "^$s=[ym]" "$CFG" && echo "WANT n, GOT $(grep -E "^$s=" "$CFG")"
  else s=${l%%=*}
    grep -qxF "$l" "$CFG" || echo "WANT $l, GOT $(grep -E "^$s=|^# $s is not set" "$CFG" || echo '(absent)')"
  fi
done
