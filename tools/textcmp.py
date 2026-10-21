#!/usr/bin/env python3
"""Compare the code of our rebuilt .ko against the device's stock .ko.

TiVo strips local symbols from its modules, so the comparison is per code section (.text,
.init.text, .exit.text) rather than per function: instruction words with relocated fields masked
(MIPS REL keeps addends in the instruction, so only the target field is masked), aligned with
difflib. The score is the share of the device's instructions matched in order.
  textcmp.py <device.ko> <our.ko> [-v]      -v: list the differing instruction runs (.text)
"""
import difflib, struct, subprocess, sys

RE, OD = 'mips-linux-gnu-readelf', 'mips-linux-gnu-objdump'
MASK = {'R_MIPS_26': 0xfc000000, 'R_MIPS_HI16': 0xffff0000, 'R_MIPS_LO16': 0xffff0000,
        'R_MIPS_PC16': 0xffff0000, 'R_MIPS_32': 0x00000000}
SECS = ('.text', '.init.text', '.exit.text')


def run(*a):
    return subprocess.run(a, capture_output=True, text=True, check=True).stdout


def load(ko):
    secs = {}
    for l in run(RE, '-W', '-S', ko).splitlines():
        p = l.replace('[ ', '[').split()
        if len(p) > 6 and p[0].startswith('[') and p[1].startswith('.'):
            secs[p[1]] = (int(p[4], 16), int(p[5], 16))
    raw = open(ko, 'rb').read()
    out = {}
    for s in SECS:
        if s not in secs: continue
        off, size = secs[s]
        out[s] = list(struct.unpack('<%dI' % (size // 4), raw[off:off + size // 4 * 4]))
    sect = None
    for l in run(RE, '-W', '-r', ko).splitlines():
        if l.startswith('Relocation section'):
            sect = l.split("'")[1][4:]   # '.rel.text' -> '.text'
            continue
        p = l.split()
        if sect in out and len(p) >= 3 and p[2] in MASK:
            i = int(p[0], 16) // 4
            if i < len(out[sect]): out[sect][i] &= MASK[p[2]]
    return out


def matched(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm, sum(m.size for m in sm.get_matching_blocks())


def main():
    dko, oko = sys.argv[1], sys.argv[2]
    dev, our = load(dko), load(oko)
    parts = []
    for s in SECS:
        d, o = dev.get(s, []), our.get(s, [])
        if not d and not o: continue
        sm, m = matched(d, o)
        parts.append('%s %d/%d %.1f%%' % (s, len(d), len(o), 100.0 * m / len(d) if d else 0))
    d, o = dev['.text'], our['.text']
    sm, m = matched(d, o)
    print('%-14s .text dev %5d ours %5d (%+d)  matched %5.1f%%  identical %s | %s' % (
        dko.rsplit('/', 1)[-1][:-3], len(d), len(o), len(o) - len(d), 100.0 * m / len(d),
        'YES' if d == o else 'no', '  '.join(parts[1:])))
    if '-v' in sys.argv:
        dd, od = dis(dko), dis(oko)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal': continue
            print('   %-7s dev[%04x:%04x] ours[%04x:%04x]' % (tag, i1 * 4, i2 * 4, j1 * 4, j2 * 4))
            for k in range(max(i2 - i1, j2 - j1))[:12]:
                a = dd.get((i1 + k) * 4, '') if i1 + k < i2 else ''
                b = od.get((j1 + k) * 4, '') if j1 + k < j2 else ''
                print('      %-44s | %s' % (a, b))


def dis(ko):
    """offset -> 'insn operands' for .text (relocation names folded in)"""
    out, last = {}, None
    for l in run(OD, '-d', '-r', '-j', '.text', ko).splitlines():
        p = l.split('\t')
        if len(p) >= 3 and p[0].strip().endswith(':'):
            last = int(p[0].strip()[:-1], 16)
            out[last] = ' '.join(x.strip() for x in p[2:])[:44]
        elif len(p) >= 2 and 'R_MIPS' in l and last is not None:
            out[last] = (out[last] + ' <' + l.split()[-1] + '>')[:44]
    return out


if __name__ == '__main__':
    main()
