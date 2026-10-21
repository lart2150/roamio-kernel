#!/bin/bash
# Build an out-of-tree kernel module for the TiVo Roamio (Linux 3.3.8-2.5, mipsel BMIPS5000).
# Usage: ./kbuild.sh <module-dir> [make args...]     e.g.  ./kbuild.sh mod/hello
set -e
MODDIR="$(realpath "${1:?usage: kbuild.sh <module-dir> [make args]}")"; shift
cd "$(dirname "$0")"
REPO=$PWD
. ./env.sh
[ -f "$MODDIR/Makefile" ] || [ -f "$MODDIR/Kbuild" ] || { echo "no Makefile/Kbuild in $MODDIR"; exit 1; }
ID="$($DOCKER image inspect -f '{{.Id}}' "$IMAGE" 2>/dev/null)" || true
[ -n "$ID" ] && [ "$(cut -d' ' -f1 $KTREE/.roamio-host 2>/dev/null)" = "$ID" ] || {
  echo "toolchain image $IMAGE missing or tree not prepared with it -> run ./prepare.sh"; exit 2; }
# extra make args go through as positional parameters, so quoting survives
$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp \
    -v "$REPO":/kbuild -v "$MODDIR":/mod "$IMAGE" bash -c '
  set -e; cd /kbuild/'"$KTREE"'
  make -j$(nproc) M=/mod modules "$@"
' kbuild "$@"
echo "built:"; ls -l "$MODDIR"/*.ko 2>/dev/null
