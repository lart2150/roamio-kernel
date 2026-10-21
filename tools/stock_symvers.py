#!/usr/bin/env python3
"""Exports of the device's stock modules -> Module.symvers format (CRC 0: no modversions).

On the Roamio, INPUT, HID, FAT and loop are modules, and bcm7429.ko exports Nexus/BXVD API, so a
module may import from a stock module rather than vmlinux. modpost and verify.py read this next to
Module.symvers.device.
  tools/stock_symvers.py <dir with stock *.ko> > symvers/Module.symvers.stock
"""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kelf import Module  # noqa: E402

rows = []
for ko in sorted(glob.glob(os.path.join(sys.argv[1], '*.ko'))):
    name = os.path.basename(ko)[:-3]
    for sym, kind in Module(ko).exports():
        rows.append((sym, name, kind))
for sym, name, kind in sorted(rows):
    print('0x00000000\t%s\t%s\t%s' % (sym, name, kind))
print('%d exports from %d modules' % (len(rows), len({r[1] for r in rows})), file=sys.stderr)
