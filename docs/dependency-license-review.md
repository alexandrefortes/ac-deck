# Dependency review for v0.1.0-preview.1

This preview uses a separately built CPython 3.13.5 without Berkeley DB or
GDBM. The former Sleepycat compatibility question is closed for this selected
interpreter by exclusion and verification; older binaries retain their
[historical review](../archive/dependency-license-review-20261102.md).
This is a technical distribution review, not professional legal approval.
Physical Steam Deck installation and performance remain untested.

## Exact distribution

The [preview release](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
provides the runtime, bootstrap, checksums and corresponding dependency-source
companion. The source tag and release record identify matching application
sources. Use this exact set together:

| Material | Identity |
| --- | --- |
| Runtime archive | 45773729 bytes; SHA-256 `f6e0b14ca8480217793d619bc7d6edb31a2666f486262681cecf301b79fbefb1` |
| Executable | SHA-256 `357309498277ddf88c2163231d5c0bfe426fb7628c895ffeca1e010e5f4201db` |
| Dependency-source companion | 385919586 bytes; SHA-256 `77a296984f0d07c5239f29630e44e7594a19899d56258a56c046f503fd260889` |
| [Dependency inventory](../licenses/dependency-sources.json) | SHA-256 `05d9cc8128641eee1ee819fd959c84c8e2444fe09f02f63be1da2a42f1487023`; 67 component records and 252 source/notice/recipe files |
| Runtime ELF inventory | 136 files, mapped to this candidate in the dependency inventory |
| Selected dependency notices | 84 original files, copied into runtime `licenses/sdk/` |

The immutable candidate must match these identities before promotion. The
[build record](build-validation.md) and [delivery workflow](community-delivery.md)
keep source tests, compiled verification, source access and publication distinct.

## Interpreter and source provenance

The new interpreter was built directly from pinned CPython source and six
exact dependency sources: OpenSSL 3.0.16, zlib 1.3.1, bzip2 1.0.8,
liblzma 5.2.12, libffi 3.4.6 and SQLite 3.47.1. Their static PIC archives are
linked into the identified Python extensions. CPython's bundled Expat,
libmpdec, HACL, mimalloc and BLAKE2 retain their original notices. The
[versioned recipe](../scripts/preparar_sdk_linux_sem_bdb.sh), source digests,
configuration and notice origins are retained in the inventory and companion.

`_dbm` and `_gdbm` are disabled; `dbm.dumb` and `dbm.sqlite3` remain available.
The reviewed SDK's 105 ELF files matched their inventory, required no DB/GDBM
library and exposed no checked DB/GDBM dynamic symbols. Its maximum required
GLIBC was 2.38; the complete runtime has its own ELF check against the product
ceiling of 2.39. The previous standalone SDK was preserved. Its files and
Berkeley DB sources are historical references, not inputs to this runtime.

The six native libraries retain their Debian/Arch origin evidence, exact
source descriptors, patches and build recipes. Pillow 12.2.0 uses the exact
pinned official wheel and full composite notice. Its identified vendor
sources are included; the original wheel cache and auditwheel rewrite were
not reproduced. Hashes identify selected bytes, not signature verification
or byte-identical rebuilding on every host.

## License routes and recipient rights

| Component or group | Selected route and supplied material |
| --- | --- |
| CPython and its six linked dependencies | Python historical/PSF terms, Apache-2.0, Zlib, bzip2, MIT and applicable public-domain material; original notices, change summary, sources and recipe retained. |
| PyInstaller 6.22.3 | GPL-2.0-or-later with its supplied exception for covered bootloader/loader files; Apache-2.0 runtime hooks. The exception does not waive other dependency obligations. |
| pyinstaller-hooks-contrib 2026.9 | Original build-hook GPL and runtime-hook Apache terms retained; a build tool's presence does not assert that every hook is embedded. |
| Shared LGPL libraries | Applicable full license/copyright notices, exact sources/patches/build material and [replacement instructions](dependency-sources.md#replacing-a-library). Recipients may modify/replace these libraries for their own use and reverse engineer the combination to debug those modifications. |
| GCC runtime libraries | GPL-3.0-or-later with GCC Runtime Library Exception 3.1; exact package sources and exception notices retained. |
| D-Bus | AFL-2.1 alternative selected, with its original notice, accompanying Expat/Tcl notices and exact source/build material; no GPL alternative selected for this library. |
| FreeType in Pillow | FTL alternative selected with full original wheel/FTL notice. This product uses FreeType and is based in part on the work of the FreeType Team. |
| Zstandard | BSD-3-Clause alternative selected for the supplied Ubuntu/wheel components; original copyright and disclaimer retained. |
| Remaining libraries and DejaVu font | Applicable per-component terms and original notices in the inventory; they do not inherit the project's purpose restrictions. |

The [D-Bus notice](../licenses/dependency-notices/ubuntu/libdbus-1-3_amd64.txt),
[Zstandard notice](../licenses/dependency-notices/ubuntu/libzstd1_amd64.txt),
[full Pillow vendor notice](../licenses/dependency-notices/sdk/sdk/pillow.txt)
and [PyInstaller terms](../licenses/dependency-notices/python-tools/pyinstaller-6.22.3.tar.gz.LICENSE)
remain intact. Corresponding sources and notices are available from the same
release as the runtime, without private repository access or a paid account.
Project-owned PolyForm terms do not supersede those component rights.

A disposable copy of this candidate accepted the existing Ubuntu ALSA 1.2.11
library in place of its 1.2.14 library. Informational CLI, `SDL_Init(0)` and
`SDL_Quit` passed; the reported version and `/proc` mapped-file hash identified
the replacement. The original candidate and SDK were unchanged. This proves
that exercised replacement mechanism, not every ABI or hardware path. Exact
hashes and observations belong to the [build record](build-validation.md).

## Content and evidence limits

The [content review](content-rights.md) retains three English quotations under
its specific US/Brazil public-domain assessment. Current public PNG gallery
payloads are omitted; historical records and local copies were preserved.
Game/DLC data, CSP, optional camera archives and private album/Toasty image/audio
are excluded. Missing optional media does not remove Rogue progression or
make optional mods prerequisites. See [integrations](third-party-integrations.md).

The public source suite records 207 tests. Compiled verification records 130
tests with no errors, failures or skips, plus ten offscreen images. Two exact
fixtures that launch Python interpreters run in the source suite and appear
as `source_process_tests` in the compiled receipt; they are not claimed as
compiled subprocess coverage. The private suite's 3,158 tests and 45 skips
are separate evidence, not public prerequisites. Automated results do not
establish real Steam Deck play or supported-release status.
