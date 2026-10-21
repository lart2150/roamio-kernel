#!/bin/bash
# Rebuild the in-tree modules TiVo ships and compare each one's code with the device's copy.
# Usage: [KCFLAGS='...'] tools/stockcmp.sh [-q] [tag]
#   (builds `make modules` in build/vm-<tag>, after ./vmbuild.sh; KCFLAGS is appended to the
#    kernel's flags, so it can override them.)  -q: one summary line (weighted by device insns)
cd "$(dirname "$0")/.."
REPO=$PWD
. ./env.sh
Q=; [ "$1" = -q ] && { Q=1; shift; }
TAG=${1:-$STBLINUX_TAG}
B=${VMDIR:-build/vm-$TAG}
DEVMOD=${DEVMOD:-$HOME/tivo-image/roamio/te4-21.11.1/unpacked/root/platform/lib/modules}
MODS="asix cdc-acm evdev fat ftdi_sio hid input-core loop nls_cp437 nls_iso8859-1 pegasus rtl8150 usbhid vfat"
$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v "$REPO":/kbuild "$IMAGE" bash -c "
  cd /kbuild/$B && make -j\$(nproc) KCFLAGS='$KCFLAGS' modules > modules.log 2>&1 || { grep -E 'error|Error' modules.log | head; exit 1; }" || exit 1
missing=
for m in $MODS; do [ -n "$(find $B -name "$m.ko" | head -1)" ] || missing="$missing $m"; done
# a missing module would silently drop out of the weighted score (and count as same-size)
[ -z "$missing" ] || { echo "not built:$missing (see $B/modules.log)" >&2; exit 1; }
out=$(for m in $MODS; do
  python3 tools/textcmp.py $DEVMOD/$m.ko $(find $B -name "$m.ko" | head -1)
done)
if [ -n "$Q" ]; then
  # fields after dropping "(+N)": 1 name 2 .text 3 dev 4 N 5 ours 6 N 7 matched 8 P% 9 identical 10 YES|no
  sed -E 's/\([+-]?[0-9]+\)//' <<<"$out" | awk -v f="$KCFLAGS" '
    {d=$4; p=$8; sub("%","",p); tot+=d; m+=d*p/100; id+=($10=="YES"); sd+=($4==$6)}
    END {printf "%-48s matched %6.2f%%  identical %2d  same-size %2d/14\n", "[" f "]", 100*m/tot, id, sd}'
else
  echo "$out"
fi
