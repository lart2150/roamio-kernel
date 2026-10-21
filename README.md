# roamio-kernel

Build environment for **out-of-tree loadable kernel modules** for the TiVo Roamio
(kernel `3.3.8-2.5`, mipsel BMIPS5000, BCM7429). Sibling of
[bolt-kernel](https://github.com/lart2150/bolt-kernel).

```
vermagic = 3.3.8-2.5 SMP mod_unload BMIPS 32BIT
```

The device kernel has **no modversions** (no `__versions` in any stock module), so there is no
CRC table to match; imports only have to resolve by name. Struct layout still has to match, and
this tree is checked against the device kernel for that (see below).

## Status

| Step | State |
|---|---|
| toolchain image, `prepare.sh`, `kbuild.sh mod/hello` | works under WSL (image ~5 min once, prepare ~6 s) |
| `hello.ko` vermagic / ELF flags vs stock `cdc-acm.ko` | identical |
| device export list (`symvers/Module.symvers.device`, 4171 vmlinux exports, CRC 0) | done |
| `verify.py` (vermagic + imports resolve against the export list) | TODO |
| base release: 2.5 vs 3.3-3.3 (`vmbuild.sh <tag>` + function-size vote) | **2.5** (device agrees with 2.5 on 29 functions, 3.3-3.3 on 8) |
| config fidelity, symbol level (`tools/symdiff.sh`) | done: device-only 1989 → 264, ours-only 4036 → 6 |
| whole-kernel struct-offset diff (`tools/offdiff.sh`) | done: no struct clusters left |
| code match of the 14 in-tree stock modules (`tools/stockcmp.sh`) | done: **99.62%**, 10 byte-identical |
| whole-kernel functions with the device's size | **99.0%** |
| load test on a Roamio | TODO |

## Usage

Needs docker. The toolchain is built from source in the image, so the docker host arch shouldn't
matter (only x86_64 has been tested).

```bash
git clone --recurse-submodules --shallow-submodules https://github.com/lart2150/roamio-kernel.git
cd roamio-kernel
./prepare.sh                     # once: builds the image (~5 min), configures, modules_prepare
./kbuild.sh mod/hello            # -> mod/hello/hello.ko
```

`prepare.sh` builds in place inside `stblinux/linux`, so the submodule is dirty afterwards
(ignored via `.gitmodules`). The tree is stamped with the toolchain image id + defconfig and
cleaned when either changes.

## Layout

| Path | What |
|---|---|
| `stblinux/` | submodule: Broadcom stblinux-3.3 @ tag `stblinux-3.3-2.5` (kernel under `linux/`) |
| `docker/Dockerfile` | CentOS 7 + GNU **gcc 4.8.3** / binutils 2.24, mipsel cross, built from source |
| `env.sh` | image name, `CROSS_COMPILE`; uses `sudo docker` only if plain `docker` doesn't work |
| `config/roamio_fragment.config` | appended to `bcm7429b0_defconfig`; derived by diffing the device kernel against our vmlinux |
| `patches/gcc48-from-3.3-3.3.patch` | the gcc-4.8 build fixes Broadcom shipped in 3.3-3.3 (`mm/page-funcs.S`, `brcmstb/memory.c` loop order); the device has the same `__clear_page_start` layout |
| `patches/tivo-weak-llsc.patch` | BMIPS5000 selects `WEAK_REORDERING_BEYOND_LLSC` (`sync` around ll/sc), as on the device |
| `patches/tivo-clear-bit-sync.patch` | `sync` after the `sc` in `clear_bit()`, as on the device |
| `patches/tivo-layout.patch` | pads `scatterlist` (+4 at 0), `request` (+4 after `deadline`), `request_queue` (+96 after `nr_batching`) to the TiVo offsets |
| `symvers/Module.symvers.device` | device vmlinux exports (names; CRC 0) from the kernel image's `__ksymtab` |
| `prepare.sh` | one-time: build image, apply `patches/`, configure, `modules_prepare` |
| `kbuild.sh <dir>` | build a module dir against the prepared tree |
| `vmbuild.sh [tag]` | full `vmlinux` of our config in `build/vm-<tag>/` (or `$VMDIR`), for diffing against the device |
| `tools/symdiff.sh` | symbol score + per-CONFIG attribution of one-sided symbols |
| `tools/offdiff.sh` | whole-kernel aligned struct-offset diff → `build/vm-<tag>/offdiff.md` |
| `tools/stockcmp.sh [-q]` | rebuild the in-tree stock modules, compare each with the device's copy |
| `tools/textcmp.py [-v]`, `tools/offscan.py` | per-module code match / diff view, struct-offset scan |
| `tools/flagsweep.sh 'flags' …` | KCFLAGS variants vs the stock modules, one summary line each |
| `tools/cfgcheck.sh <.config>` | fragment lines that didn't survive `oldconfig` |
| `tools/ptype.sh <obj> 'struct x'` | field offsets from our tree (`-g` compile + gdb `ptype /o`) |
| `tools/dis_fn.sh dev\|ours <fn>` | disassemble one function from the device image or our vmlinux |
| `mod/hello/` | smoke-test module |

The analysis tools use the device kernel unpacked in the tivo-image repo
(`roamio/te4-21.11.1/kernel/{Image,kallsyms.txt}`, stock modules under
`roamio/te4-21.11.1/unpacked/root/platform/lib/modules`) and its `tools/` (`sym_diff.py`,
`roamio_symscore.py`, `mips_align_offset_diff.py`, `roamio_kextract.py`).

## Toolchain

The device banner is
`Linux version 3.3.8-2.5 (build@jenkslave-client18) (gcc version 4.8.3 (GCC) )`. "(GCC)" with no
vendor pkgversion means an unmodified GNU release build, so the image builds exactly that: gcc
4.8.3 and binutils 2.24 (contemporary, May 2014 / Dec 2013) from ftp.gnu.org. The tarballs were
checked against their GNU signatures (gcc: Richard Guenther `3AB00996FC26A641`, binutils: Tristan
Gingold `C3126D3B4AE55E93`) and their sha256s are pinned in the Dockerfile. C only, no libc: the
kernel needs neither libc nor libgcc. Our kernel banner reads the same `gcc version 4.8.3 (GCC)`.

CentOS 7 (`centos:7`, packages from vault.centos.org) keeps 3.3-era host tools: perl 5.16
(`kernel/timeconst.pl` fails on perl >= 5.22) and make 3.82. The base image does not affect the
generated code; it only provides host tools.

This binutils' `nm` writes sign-extended 64-bit addresses (`ffffffff8…`) into `System.map`; the
tools mask them.

**History:** this env started on Broadcom's prebuilt `stbgcc-4.8-0.5` (a `4.8.3 20140401
(prerelease)` snapshot; no distro shipped a 4.8.3 MIPS cross compiler). Against the stock modules:

| | stbgcc-4.8-0.5 | **GNU gcc 4.8.3** |
|---|---|---|
| stock modules matched (weighted) | 98.49% | **99.62%** |
| byte-identical modules | 6 | **10** |
| whole-kernel same-size functions | 96.3% | **99.0%** |

Before switching, `tools/flagsweep.sh` ruled out flags: 33 KCFLAGS variants (every `-mtune`, `-Os`,
scheduling, block reordering, inlining, IPA, loop, IRA, …) all matched worse or the same. The
stock Kbuild flags (`-O2 -march=mips32 -mlong-calls -msoft-float -G 0 -fno-pic`, no `-mtune`) are
TiVo's. Neither side uses MIPS32r2 instructions.

## Stock module code match

`tools/stockcmp.sh` builds the 14 in-tree modules TiVo ships, in the `vmbuild.sh` tree, and
compares each with the device's copy. `tools/textcmp.py` masks relocated fields and reports the
share of the device's instructions matched in order. TiVo strips local symbols, so the comparison
is per section, not per function.

| module | .text insns dev / ours | matched |
|---|---|---|
| cdc-acm, evdev, fat, ftdi_sio, input-core, loop, usbhid, vfat, nls_cp437, nls_iso8859-1 | same | **100% (byte-identical)** |
| hid | 13672 / 13672 | 100.0% (a few words differ) |
| asix | 2676 / 2640 | 98.4% |
| pegasus | 3308 / 3276 | 97.8% |
| rtl8150 | 2128 / 2096 | 95.1% |

Overall (weighted by device instructions, `tools/stockcmp.sh -q`): **99.62%**. Every
`.init.text`/`.exit.text` matches 100%.

asix, pegasus and rtl8150 differ by a **TiVo source change**: their `*_ioctl()` handles an extra
private command `0x89ff` (`SIOCDEVPRIVATE+15`, `CAP_NET_ADMIN`) that copies the adapter's USB
`idVendor`/`idProduct` to user space. No layout implications. The device modules also leak TiVo's
build tree: `/cde/hudson/workspace/b-tcdkernel-mira-4-12-release-mipsel/srcroot/os/linux-3/3.3/`.

TiVo's modules have no `.pdr`/`.comment` sections (ours have both); they are stripped (no local
symbols either), which does not affect code.

Not compared: proprietary modules (`bcm7429`, `tv_bcm7429`, `frontpanel`, `gpio`, `ircatch`,
`router`, `mpod`, `ubuddy`), TiVo-only GPL source (`ad-iosched`, `hid-tivo`, `znusb`), and modules
without vermagic, i.e. built against another kernel (`bcmdhd`, `btusb`, `bthid`, `tr`).

## Barriers

- `tivo-weak-llsc.patch`: TiVo's kernel emits `sync` around every ll/sc sequence
  (`CONFIG_WEAK_REORDERING_BEYOND_LLSC`). The option is a hidden bool that no Broadcom 3.3 release
  selects for BMIPS5000, so it takes a Kconfig patch.
- `tivo-clear-bit-sync.patch`: TiVo also puts a `sync` straight after the `sc` of `clear_bit()`,
  inside the retry loop: 374 sites in the device kernel (153 `and`, 221 `li ~mask; and`), 0 in stock.
  No other bitop or atomic has it, and no Broadcom release (3.3 2.5–4.4, 3.14) has it. Probably a
  BMIPS5000 workaround, so module code needs it too. Our vmlinux has exactly 153 + 221 sites.

Without these, our modules would lack barriers the rest of the kernel has (rare SMP-only
failures rather than obvious crashes).

## Config fidelity (symbol level)

`tools/symdiff.sh` compares the device kallsyms (decoded from the kernel image) with our
System.map and attributes each one-sided symbol to the `CONFIG_*` that gates it. Highlights of what
`bcm7429b0_defconfig` had wrong:

- struct-relevant: `DEBUG_SPINLOCK`, `DEBUG_MUTEXES`, `DEBUG_KMEMLEAK`, `HIGHMEM`, `PM_RUNTIME`,
  netfilter/conntrack, `NET_SCHED`, `SCHEDSTATS` (`task_struct`), no `HIGH_RES_TIMERS`
- built in on the device: usbnet, fuse, ext2/ext3 + JBD, squashfs (xz/lzo), cfg80211, TUN, USB serial core
- modules on the device: INPUT core, HID (+ `HIDRAW`, `USB_HIDDEV`), FAT/VFAT, loop, NLS, asix/pegasus/rtl8150, cdc-acm, ftdi_sio
- absent on the device: MTD (all of it), SPI, MoCA (Broadcom's), NFS/SUNRPC, bridge, ext4, VT, USB_MON, CFQ/deadline

The 264 device-only symbols left are TiVo source, not config: Entropic c.LINK MoCA built in
(`Clnk_*`, `HostOS_*`, `emoca_*`), crashall / panic log / `contigmem` / gioctl / `tivo_partition`,
AHCI core-dump-to-swap, an Atheros switch (`athsw_*`), cmdline whitelisting, and block-layer write
credits (`queue_credit_*`, `queue_writes_per_sec_*`, `queue_requests_{read,write}_*`).

## Whole-kernel struct-offset diff

`tools/offdiff.sh` runs tivo-image `tools/mips_align_offset_diff.py`, the MIPS port of the Bolt
`align_offset_diff.py`. It aligns about 12.6k functions present in both kernels, with immediates
masked, and records every aligned load/store/addiu pair whose offset differs (182k pairs). A moved
field shows up as the same (ours → device) pair across many functions. `%lo(symbol)` immediates are
excluded by tracking registers loaded with `lui`. The big leftover deltas (+16384, −49152, …) are
absolute addresses whose `lui` the tracker doesn't see, so they are noise.

| Cluster (ours → device) | Cause | Fix |
|---|---|---|
| `scatterlist` +4 from offset 0; `ata_queued_cmd` +4 and `ata_port` +128 (= `qcmd[32]` × 4) | TiVo field at the head of `struct scatterlist`. It is the `DEBUG_SG` layout, but the device never writes or checks `SG_MAGIC` (`sg_init_table`/`sg_next` have no magic store and no trap) | pad in `tivo-layout.patch`, `DEBUG_SG` off |
| `usb_device` −4 from 0x2ec (`quirks` 0x304 → 0x300) | `usb_device.usb_classdev` | `# CONFIG_USB_DEVICE_CLASS is not set` |
| `request` +4 from `timeout_list` (0xbc) | TiVo field after `deadline` | pad in `tivo-layout.patch` |
| `request_queue` +96 from `dma_drain_size` (0x320): tags, timeout, `limits`, `flush_rq` | TiVo per-direction request limits / congestion thresholds after `nr_requests` (device `blk_queue_congestion_threshold` reads 784/788 and writes 792–804; `queue_requests_{read,write}_*` sysfs) | 96-byte pad after `nr_batching`. **`nr_congestion_on/off`, `nr_batching` keep our offsets and must not be used from modules** |

After the fixes no cluster remains; with gcc 4.8.3 there are no small-delta rows at all. BUG
traps: ours 1370 `tne` / 223 `break`, device 1371 / 225.
