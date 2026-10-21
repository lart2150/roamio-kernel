#!/bin/bash
# One-time prepare of the TiVo Roamio kernel tree (stblinux-3.3-2.5) for out-of-tree module builds.
# Builds the toolchain image if missing, applies patches/, configures, modules_prepare.
set -e
cd "$(dirname "$0")"
REPO=$PWD
. ./env.sh
DEFCONFIG=${DEFCONFIG:-bcm7429b0_defconfig}

[ -f $KTREE/Makefile ] || git submodule update --init stblinux
# host networking: under WSL the DNS stub isn't reachable from the default bridge
$DOCKER image inspect "$IMAGE" >/dev/null 2>&1 || \
  $DOCKER build --network host -t "$IMAGE" docker/

for p in patches/*.patch; do
  [ -e "$p" ] || continue
  if patch -d $KTREE -p1 -R -s -f --dry-run < "$p" >/dev/null 2>&1; then
    echo "$(basename "$p") already applied"
  else
    patch -d $KTREE -p1 -N --no-backup-if-mismatch < "$p"
  fi
done

# the prepared tree holds compiler-dependent output: clean it if another toolchain image prepared it
STAMP="$($DOCKER image inspect -f '{{.Id}}' "$IMAGE") $DEFCONFIG"
CLEAN=
[ -f $KTREE/.roamio-host ] && [ "$(cat $KTREE/.roamio-host)" != "$STAMP" ] && CLEAN="make mrproper"

$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v "$REPO":/kbuild "$IMAGE" bash -c "
  set -e; cd /kbuild/$KTREE
  $CLEAN
  make -j\$(nproc) $DEFCONFIG >/dev/null
  cat /kbuild/config/roamio_fragment.config >> .config
  yes '' | make -j\$(nproc) oldconfig >/dev/null
  make -j\$(nproc) modules_prepare
  [ -f /kbuild/symvers/Module.symvers.device ] && cp /kbuild/symvers/Module.symvers.device ./Module.symvers
  echo PREPARED: \$(sed -n 's/.*\"\(.*\)\"/\1/p' include/generated/utsrelease.h) with \$(\${CROSS_COMPILE}gcc --version | head -1)
"
echo "$STAMP" > $KTREE/.roamio-host
