#!/bin/bash
# Struct layout (offsets/sizes) from our tree: compile one object with -g, then gdb `ptype /o`.
# Usage: tools/ptype.sh <object.o in kernel tree> 'struct foo' ['struct bar' ...]
#   e.g. tools/ptype.sh block/blk-core.o 'struct request_queue' 'struct request'
cd "$(dirname "$0")/.."
REPO=$PWD
. ./env.sh
OBJ=$1; shift
B=${VMDIR:-build/vm-$STBLINUX_TAG}
$DOCKER run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v "$REPO":/kbuild "$IMAGE" bash -c "
  set -e; cd /kbuild/$B; D=\$(dirname $OBJ)
  # 3.3's single-object target falls through to make's implicit rule here, so build the directory
  # with -g, keep the one object, then rebuild the directory normally (no -g objects left behind)
  make KCFLAGS=-g \$D/ > /kbuild/build/ptype.log 2>&1; cp $OBJ /kbuild/build/ptype.o
  make \$D/ >> /kbuild/build/ptype.log 2>&1" \
  || { tail -5 build/ptype.log; exit 1; }
for s in "$@"; do
  gdb-multiarch -batch -ex "set architecture mips:isa32" -ex "ptype /o $s" build/ptype.o 2>/dev/null
done
