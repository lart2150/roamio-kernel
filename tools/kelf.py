"""Minimal ELF32 little-endian reader for kernel modules (no binutils needed).

Just what verify.py / stock_symvers.py need: section headers, symbols, REL relocations,
.modinfo and the GNU attributes section.
"""
import struct

SHT_SYMTAB, SHT_REL, SHT_GNU_ATTRIBUTES = 2, 9, 0x6ffffff5
SHN_UNDEF = 0
STB_GLOBAL, STB_WEAK = 1, 2
EM_MIPS = 8


class Section:
    def __init__(self, idx, name, typ, flags, addr, off, size, link, info, align, entsize):
        self.idx, self.name, self.type, self.flags = idx, name, typ, flags
        self.offset, self.size, self.link, self.info, self.entsize = off, size, link, info, entsize


class Symbol:
    def __init__(self, idx, name, value, size, info, shndx):
        self.idx, self.name, self.value, self.size, self.shndx = idx, name, value, size, shndx
        self.bind, self.type = info >> 4, info & 0xf


class Module:
    def __init__(self, path):
        self.path = path
        d = self.data = open(path, 'rb').read()
        if d[:4] != b'\x7fELF':
            raise ValueError('%s: not an ELF file' % path)
        self.ei_class, self.ei_data = d[4], d[5]
        if self.ei_class != 1 or self.ei_data != 1:
            raise ValueError('%s: not ELF32 little-endian (class %d, data %d)' % (path, d[4], d[5]))
        (self.e_type, self.e_machine, _, _, _, shoff, self.e_flags, _, _, _, shentsize, shnum,
         shstrndx) = struct.unpack_from('<HHIIIIIHHHHHH', d, 16)
        raw = [struct.unpack_from('<IIIIIIIIII', d, shoff + i * shentsize) for i in range(shnum)]
        strtab = raw[shstrndx][4]
        self.sections = [Section(i, self._str(strtab, r[0]), *r[1:]) for i, r in enumerate(raw)]
        self.by_name = {s.name: s for s in self.sections}
        self._syms = None

    def _str(self, off, idx):
        e = self.data.index(b'\0', off + idx)
        return self.data[off + idx:e].decode('latin1')

    def section_data(self, name):
        s = self.by_name.get(name)
        return self.data[s.offset:s.offset + s.size] if s else b''

    def symbols(self):
        if self._syms is None:
            st = next((s for s in self.sections if s.type == SHT_SYMTAB), None)
            self._syms = []
            if st:
                strtab = self.sections[st.link].offset
                for i in range(st.size // 16):
                    nm, val, size, info, _, shndx = struct.unpack_from('<IIIBBH', self.data, st.offset + 16 * i)
                    self._syms.append(Symbol(i, self._str(strtab, nm), val, size, info, shndx))
        return self._syms

    def undefined(self):
        """imported symbols: global/weak, undefined, named"""
        return [s for s in self.symbols() if s.shndx == SHN_UNDEF and s.name and s.bind in (STB_GLOBAL, STB_WEAK)]

    def relocations(self):
        """yield (target section, r_offset, type, Symbol) for every REL entry"""
        syms = self.symbols()
        for rs in self.sections:
            if rs.type != SHT_REL:
                continue
            tgt = self.sections[rs.info]
            for i in range(rs.size // 8):
                off, info = struct.unpack_from('<II', self.data, rs.offset + 8 * i)
                yield tgt, off, info & 0xff, syms[info >> 8]

    def modinfo(self):
        out = {}
        for f in self.section_data('.modinfo').split(b'\0'):
            if b'=' in f:
                k, v = f.split(b'=', 1)
                out.setdefault(k.decode(), []).append(v.decode('latin1'))
        return out

    def gnu_attributes(self):
        """{tag: value} from the 'gnu' vendor File subsection (e.g. 4 = Tag_GNU_MIPS_ABI_FP)"""
        s = next((s for s in self.sections if s.type == SHT_GNU_ATTRIBUTES), None)
        if not s:
            return {}
        d = self.data[s.offset:s.offset + s.size]
        out, p = {}, 1                                       # d[0] == 'A'
        while p < len(d):
            ln = struct.unpack_from('<I', d, p)[0]
            vend_end = d.index(b'\0', p + 4)
            if d[p + 4:vend_end] == b'gnu':
                q = vend_end + 1
                while q < p + ln:
                    tag, sublen = d[q], struct.unpack_from('<I', d, q + 1)[0]
                    if tag == 1:                             # Tag_File
                        r = q + 5
                        while r < q + sublen:
                            t, r = _uleb(d, r)
                            v, r = _uleb(d, r)
                            out[t] = v
                    q += sublen
            p += ln
        return out

    def exports(self):
        """[(name, 'EXPORT_SYMBOL'|'EXPORT_SYMBOL_GPL')] from __ksymtab / __ksymtab_gpl (works on stripped
        modules: each kernel_symbol's name pointer is an R_MIPS_32 into __ksymtab_strings)"""
        strs = self.by_name.get('__ksymtab_strings')
        if not strs:
            return []
        out = []
        for tgt, off, typ, sym in self.relocations():
            if tgt.name not in ('__ksymtab', '__ksymtab_gpl') or off % 8 != 4 or typ != 2:
                continue
            if self.sections[sym.shndx].name != '__ksymtab_strings':
                continue
            addend = struct.unpack_from('<I', self.data, tgt.offset + off)[0]
            out.append((self._str(strs.offset, sym.value + addend),
                        'EXPORT_SYMBOL_GPL' if tgt.name == '__ksymtab_gpl' else 'EXPORT_SYMBOL'))
        return out


def _uleb(d, p):
    v = shift = 0
    while True:
        b = d[p]; p += 1
        v |= (b & 0x7f) << shift; shift += 7
        if not b & 0x80:
            return v, p
