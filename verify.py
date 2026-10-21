#!/usr/bin/env python3
"""Will a .ko load on the TiVo Roamio (3.3.8-2.5, mipsel BMIPS5000)? Static go/no-go, no binutils.

The device kernel has no modversions, so there are no CRCs to match. Checked instead, following
what the 3.3 loader (kernel/module.c, arch/mips/kernel/module.c) actually does:
  - vermagic is exactly the device's (strcmp, trailing space included). A *missing* vermagic still
    loads (and taints the kernel): the device has CONFIG_MODULE_FORCE_LOAD, which is how TiVo's
    bcmdhd/btusb/mpod/... load
  - ELF32 LE MIPS, o32, MIPS32 (not R2: the kernel is -march=mips32), not PIC/abicalls
  - no FPU instructions (the kernel runs with the FPU off). The soft/hard-float attribute itself is
    only a note: several of TiVo's own modules are tagged hard-float and contain no FPU code
  - struct module (.gnu.linkonce.this_module) is the device's size
  - only relocation types the MIPS loader handles (NONE/32/26/HI16/LO16) in allocated sections:
    it indexes its handler table with the raw type, so anything else oopses at insmod
  - no R_MIPS_26 (jal/j) against an imported symbol: modules load in vmalloc space, far from the
    kernel, so those fail with "relocation overflow" (Kbuild's -mlong-calls avoids them)
  - no common symbols (the loader rejects them: "please compile with -fno-common"), and no symbol
    in another reserved section index (MIPS small common 0xff03 is what -fcommon gives after
    `ld -r`; the loader would use it as an index into the section table)
  - every non-weak import is exported by vmlinux, a stock module (load it first), or a sibling
    module in the same directory (its Module.symvers); unresolved weak imports are allowed
  - GPL-only imports only from a GPL-compatible module
  - no export that vmlinux already exports ("exports duplicate symbol"); one a stock module exports
    means that stock module must not be loaded at the same time
Usage: verify.py <module.ko> [more.ko ...]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
from kelf import Module, EM_MIPS, STB_WEAK  # noqa: E402

VERMAGIC = '3.3.8-2.5 SMP mod_unload BMIPS 32BIT '   # exact: the loader strcmp()s, trailing space included
THIS_MODULE_SIZE = 0x13c          # sizeof(struct module), same in every stock TiVo module
EF_MIPS_ARCH, E_MIPS_ARCH_32, EF_MIPS_ABI, E_MIPS_ABI_O32 = 0xf0000000, 0x50000000, 0x0000f000, 0x00001000
EF_MIPS_PIC, EF_MIPS_CPIC = 0x2, 0x4
TAG_GNU_MIPS_ABI_FP, FP_SOFT = 4, 3
R_MIPS_26 = 4
LOADER_RELOCS = {0: 'NONE', 2: 'R_MIPS_32', 4: 'R_MIPS_26', 5: 'R_MIPS_HI16', 6: 'R_MIPS_LO16'}
SHF_ALLOC, SHF_EXECINSTR, SHT_PROGBITS, SHN_ABS, SHN_COMMON = 0x2, 0x4, 1, 0xfff1, 0xfff2
FPU_OPS = {0x11, 0x13, 0x31, 0x35, 0x39, 0x3d}   # COP1, COP1X, lwc1, ldc1, swc1, sdc1
GPL_COMPAT = {'GPL', 'GPL v2', 'GPL and additional rights', 'Dual BSD/GPL', 'Dual MIT/GPL', 'Dual MPL/GPL'}
SYMVERS = ('Module.symvers.device', 'Module.symvers.stock')


def load_symvers(path, table, skip_module=None):
    """name -> (owner, gpl_only); first table wins. skip_module: don't take a module's own exports."""
    for line in open(path):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 4 and p[1] not in table and os.path.basename(p[2]) != skip_module:
            table[p[1]] = (os.path.basename(p[2]), p[3].endswith('_GPL'))


def device_table():
    table = {}
    for f in SYMVERS:
        path = os.path.join(HERE, 'symvers', f)
        if not os.path.exists(path):
            sys.exit('missing %s (regenerate: see README)' % path)
        load_symvers(path, table)
    return table


def fpu_insns(m):
    n = 0
    for s in m.sections:
        if s.type == SHT_PROGBITS and s.flags & SHF_EXECINSTR:
            d = m.data[s.offset:s.offset + s.size]
            n += sum(1 for i in range(0, len(d) - 3, 4) if (d[i + 3] >> 2) in FPU_OPS)
    return n


def check(ko, devtable):
    problems, notes = [], []
    m = Module(ko)
    name = os.path.basename(ko)[:-3]
    if m.e_machine != EM_MIPS:
        problems.append('e_machine %d, not MIPS' % m.e_machine)
    f = m.e_flags
    if f & EF_MIPS_ARCH != E_MIPS_ARCH_32:
        problems.append('ISA flags %#x, want MIPS32 (0x50000000; R2 instructions trap on this kernel build)' % (f & EF_MIPS_ARCH))
    if f & EF_MIPS_ABI != E_MIPS_ABI_O32:
        problems.append('ABI flags %#x, want o32' % (f & EF_MIPS_ABI))
    if f & (EF_MIPS_PIC | EF_MIPS_CPIC):
        problems.append('PIC/abicalls object (flags %#x); kernel modules must be -mno-abicalls -fno-pic' % f)
    fp = m.gnu_attributes().get(TAG_GNU_MIPS_ABI_FP)
    if fp not in (None, FP_SOFT):
        notes.append('tagged Tag_GNU_MIPS_ABI_FP = %d (not soft-float); harmless unless FPU code is present' % fp)
    nfp = fpu_insns(m)
    if nfp:
        problems.append('%d FPU instruction(s) in code (cop1/lwc1/swc1/ldc1/sdc1): build with -msoft-float' % nfp)

    mi = m.modinfo()
    vm = mi['vermagic'][0] if 'vermagic' in mi else None
    if vm is None:
        notes.append('no vermagic: loads only via CONFIG_MODULE_FORCE_LOAD (device has it) and taints the kernel')
    elif vm != VERMAGIC:
        problems.append('vermagic %r, want %r' % (vm, VERMAGIC))
    lic = (mi.get('license') or [''])[0]
    tm = m.by_name.get('.gnu.linkonce.this_module')
    if not tm:
        problems.append('no .gnu.linkonce.this_module (not a kernel module?)')
    elif tm.size != THIS_MODULE_SIZE:
        problems.append('struct module is %#x bytes, device has %#x (layout mismatch)' % (tm.size, THIS_MODULE_SIZE))
    if m.by_name.get('__versions'):
        notes.append('has __versions (modversions); the device kernel ignores them')

    syms = m.symbols()
    common = sorted(s.name for s in syms if s.shndx == SHN_COMMON)
    if common:
        problems.append('common symbol(s), the loader rejects them (compile with -fno-common): %s' % ' '.join(common[:20]))
    # simplify_symbols() only special-cases UNDEF/ABS/COMMON; any other index is used as
    # sechdrs[st_shndx], so a reserved one (MIPS SHN_MIPS_SCOMMON 0xff03 = small common, what
    # -fcommon gives after `ld -r`) reads past the section table
    odd = sorted('%s (%#x)' % (s.name, s.shndx) for s in syms
                 if s.shndx >= len(m.sections) and s.shndx not in (SHN_ABS, SHN_COMMON))
    if odd:
        problems.append('symbol(s) in a reserved section index the loader would index sechdrs[] with '
                        '(0xff03 = MIPS small common: compile with -fno-common): %s' % ' '.join(odd[:20]))

    table = dict(devtable)
    sib = os.path.join(os.path.dirname(os.path.abspath(ko)), 'Module.symvers')
    if os.path.exists(sib):
        load_symvers(sib, table, skip_module=name)
    und = m.undefined()
    imports = sorted({s.name for s in und})
    weak = {s.name for s in und if s.bind == STB_WEAK}
    missing = [s for s in imports if s not in table and s not in weak]
    weak_unres = [s for s in imports if s not in table and s in weak]
    gpl = [s for s in imports if s in table and table[s][1]]
    if missing:
        problems.append('%d import(s) not exported by vmlinux or any stock/sibling module: %s'
                        % (len(missing), ' '.join(missing[:20])))
    if weak_unres:
        notes.append('weak import(s) nothing exports (allowed, resolve to 0): %s' % ' '.join(weak_unres[:20]))
    if gpl and lic not in GPL_COMPAT:
        problems.append('license %r is not GPL-compatible but imports GPL-only: %s' % (lic, ' '.join(gpl[:20])))
    deps = {}
    for s in imports:
        if s in table and table[s][0] != 'vmlinux':
            deps.setdefault(table[s][0], []).append(s)

    dup_k, dup_m = [], {}
    for s, _ in m.exports():
        owner = devtable.get(s, (None,))[0]
        if owner == 'vmlinux':
            dup_k.append(s)
        elif owner and owner != name:
            dup_m.setdefault(owner, []).append(s)
    if dup_k:
        problems.append('exports symbol(s) vmlinux already exports (loader: "exports duplicate symbol"): %s'
                        % ' '.join(dup_k[:20]))
    for owner, ss in sorted(dup_m.items()):
        notes.append('exports %d symbol(s) stock %s.ko also exports: it cannot be loaded while %s is' % (len(ss), owner, owner))

    badrel, far = {}, set()
    for tgt, off, typ, sym in m.relocations():
        if not tgt.flags & SHF_ALLOC:
            continue                  # the loader skips relocations for non-allocated sections (.pdr, debug)
        if typ not in LOADER_RELOCS:
            badrel.setdefault(typ, set()).add(tgt.name)
        elif typ == R_MIPS_26 and sym.shndx == 0 and sym.name:
            far.add(sym.name)
    for typ, secs in sorted(badrel.items()):
        problems.append('relocation type %d in %s: the MIPS loader only handles %s and would oops on it'
                        % (typ, ' '.join(sorted(secs)), '/'.join(LOADER_RELOCS.values())))
    if far:
        problems.append('R_MIPS_26 (jal) to imported symbol(s), fails to relocate (build with -mlong-calls): %s'
                        % ' '.join(sorted(far)[:20]))

    print('ko:        ', ko)
    print('vermagic:  ', repr(vm), '->', 'OK' if vm == VERMAGIC else 'MISSING (force-load)' if vm is None else 'MISMATCH')
    print('license:   ', repr(lic), '| struct module', hex(tm.size) if tm else '-',
          '| flags %#x' % f, '| imports', len(imports), '(%d GPL-only)' % len(gpl))
    for mod, ss in sorted(deps.items()):
        print('needs %s loaded first for: %s' % (mod, ' '.join(ss[:12]) + (' …' if len(ss) > 12 else '')))
    for n in notes:
        print('note:', n)
    for p in problems:
        print('PROBLEM:', p)
    ok = not problems
    print('WILL LOAD ON ROAMIO:', 'YES' if ok else 'NO (fix the above)')
    return ok


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    devtable = device_table()
    res = [check(k, devtable) for k in sys.argv[1:]]
    sys.exit(0 if all(res) else 1)
