#!/bin/bash
# Build a full vmlinux of our config in a separate tree, for diffing against the device kernel
# (symbols, sizes, initcalls). Leaves the prepared module tree alone.
# Usage: [VMDIR=dir] ./vmbuild.sh [tag]      default tag = $STBLINUX_TAG (the submodule's release)
#   -> build/vm-<tag>/{vmlinux,System.map,.config}; patches/ are applied only to $STBLINUX_TAG.
#   Other tags need a full (non-shallow) submodule clone.
set -e
cd "$(dirname "$0")"
REPO=$PWD
. ./env.sh
DEFCONFIG=${DEFCONFIG:-bcm7429b0_defconfig}
TAG=${1:-$STBLINUX_TAG}
B=${VMDIR:-build/vm-$TAG}
if [ ! -f $B/Makefile ]; then
  # extract + patch into a temp dir and only then move it into place, so a failed patch can't
  # leave a half-patched tree that later runs would build as if it were complete
  rm -rf $B.tmp; mkdir -p $B.tmp
  if [ "$TAG" = "$STBLINUX_TAG" ]; then
    git -C stblinux archive HEAD linux | tar -x -C $B.tmp --strip-components=1
    for p in patches/*.patch; do [ -e "$p" ] && patch -s -d $B.tmp -p1 -N --no-backup-if-mismatch < "$p"; done
  else
    git -C stblinux archive $TAG linux | tar -x -C $B.tmp --strip-components=1
  fi
  rm -rf $B; mv $B.tmp $B
fi
$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v "$REPO":/kbuild "$IMAGE" bash -c "
  set -e; cd /kbuild/$B
  make -j\$(nproc) $DEFCONFIG >/dev/null
  cat /kbuild/config/roamio_fragment.config >> .config
  yes '' | make -j\$(nproc) oldconfig >/dev/null
  make -j\$(nproc) vmlinux > build.log 2>&1 || { grep -E 'error|Error' build.log | head -30; exit 1; }
  ls -l vmlinux System.map
"
