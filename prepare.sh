#!/bin/bash
# One-time prepare of the TiVo Roamio kernel tree (stblinux-3.3-2.5) for out-of-tree module builds.
# Builds the toolchain image if missing, applies patches/, configures, modules_prepare.
# If the toolchain image, defconfig, patches/, the config fragment or symvers/ changed since the
# last prepare, stblinux/linux is reset to the pinned release first (generated files and the
# applied patches only: don't keep hand edits in there).
set -e
cd "$(dirname "$0")"
REPO=$PWD
. ./env.sh
DEFCONFIG=${DEFCONFIG:-bcm7429b0_defconfig}

[ -f $KTREE/Makefile ] || git submodule update --init stblinux
# host networking: under WSL the DNS stub isn't reachable from the default bridge
$DOCKER image inspect "$IMAGE" >/dev/null 2>&1 || \
  $DOCKER build --network host -t "$IMAGE" docker/

STAMP="$(tree_stamp)"
if [ -f $KTREE/.roamio-host ] && [ "$(cat $KTREE/.roamio-host)" != "$STAMP" ]; then
  echo "toolchain/defconfig/patches/fragment/symvers changed since the last prepare: resetting $KTREE"
  git -C stblinux checkout -q -- linux
  git -C stblinux clean -fdxq -- linux
fi

for p in patches/*.patch; do
  [ -e "$p" ] || continue
  if patch -d $KTREE -p1 -R -s -f --dry-run < "$p" >/dev/null 2>&1; then
    echo "$(basename "$p") already applied"
  else
    patch -d $KTREE -p1 -N --no-backup-if-mismatch < "$p"
  fi
done

$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v "$REPO":/kbuild "$IMAGE" bash -c "
  set -e; cd /kbuild/$KTREE
  make -j\$(nproc) $DEFCONFIG >/dev/null
  cat /kbuild/config/roamio_fragment.config >> .config
  yes '' | make -j\$(nproc) oldconfig >/dev/null
  make -j\$(nproc) modules_prepare
  # device vmlinux exports + the stock modules' (INPUT/HID/FAT/loop/bcm7429 are modules on the device),
  # so modpost resolves imports the way the box will
  cat /kbuild/symvers/Module.symvers.device /kbuild/symvers/Module.symvers.stock > ./Module.symvers
  echo PREPARED: \$(sed -n 's/.*\"\(.*\)\"/\1/p' include/generated/utsrelease.h) with \$(\${CROSS_COMPILE}gcc --version | head -1)
"
echo "$STAMP" > $KTREE/.roamio-host
