#!/bin/bash
# Build an out-of-tree kernel module for the TiVo Roamio (Linux 3.3.8-2.5, mipsel BMIPS5000).
# Usage: ./kbuild.sh <module-dir> [make args...]     e.g.  ./kbuild.sh mod/hello
set -e
MODDIR="$(realpath "${1:?usage: kbuild.sh <module-dir> [make args]}")"; shift
cd "$(dirname "$0")"
REPO=$PWD
. ./env.sh
[ -f "$MODDIR/Makefile" ] || [ -f "$MODDIR/Kbuild" ] || { echo "no Makefile/Kbuild in $MODDIR"; exit 1; }
$DOCKER image inspect "$IMAGE" >/dev/null 2>&1 || { echo "toolchain image $IMAGE missing -> run ./prepare.sh"; exit 2; }
[ "$(cat $KTREE/.roamio-host 2>/dev/null)" = "$(tree_stamp)" ] || {
  echo "tree not prepared, or prepared with another toolchain/defconfig/patches/fragment/symvers -> run ./prepare.sh"; exit 2; }
# extra make args go through as positional parameters, so quoting survives
$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp \
    -v "$REPO":/kbuild -v "$MODDIR":/mod "$IMAGE" bash -c '
  set -e; cd /kbuild/'"$KTREE"'
  make -j$(nproc) M=/mod modules "$@"
' kbuild "$@"
echo "built:"; ls -l "$MODDIR"/*.ko 2>/dev/null
