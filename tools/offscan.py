#!/usr/bin/env python3
"""Struct-offset scan: in aligned code (textcmp.py), list instruction pairs that are the same
load/store/addiu with the same registers but a different immediate -- the signature of a field at
a different offset. Prints each (device offset -> our offset) delta with a count.
  offscan.py <device.ko> <our.ko>
"""
import collections, re, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from textcmp import load, matched, dis  # noqa: E402

MEM = re.compile(r'^(l[bhw]u?|s[bhw]|lwl|lwr|swl|swr|ll|sc|addiu)\s+(\S+),(-?\d+)(\(\w+\)|,\w+)?$')


def key(s):
    m = MEM.match(s.split(' <')[0])
    return (m.group(1), m.group(2), m.group(4), int(m.group(3))) if m else None


dko, oko = sys.argv[1:3]
dev, our = load(dko)['.text'], load(oko)['.text']
dd, od = dis(dko), dis(oko)
sm, _ = matched(dev, our)
deltas = collections.Counter(); ex = {}
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag != 'replace': continue
    for k in range(min(i2 - i1, j2 - j1)):
        a, b = key(dd.get((i1 + k) * 4, '')), key(od.get((j1 + k) * 4, ''))
        if a and b and a[:3] == b[:3] and a[3] != b[3]:
            d = (a[3], b[3]); deltas[d] += 1
            ex.setdefault(d, '%s @dev %04x' % (dd[(i1 + k) * 4], (i1 + k) * 4))
name = dko.rsplit('/', 1)[-1][:-3]
if not deltas: print('%-14s no offset-only differences' % name)
for (a, b), n in sorted(deltas.items(), key=lambda x: (x[0][0] - x[0][1], x[0][0])):
    print('%-14s dev %5d ours %5d (dev %+d) x%-3d e.g. %s' % (name, a, b, a - b, n, ex[(a, b)]))
