> Historical review recorded on 2 November 2026. Its hashes and conclusions
> apply only to the earlier candidates described below. The new interpreter
> does not approve those binaries. Follow the [current review](../docs/dependency-license-review.md)
> for v0.1.0-preview.1. Links to the current dependency inventory are navigation,
> not a claim that its newer bytes match the historical inventory hashes here.

# Dependency review for the reconciled candidate

The reviewed local candidates are **not ready for binary publication**.
Complete reviewed source material, a 95-file notice selection and replacement
instructions are now prepared; exact runtime integration and recipient access
remain separate. Berkeley DB compatibility remains open. This is a
technical evidence review, not legal approval. Physical Deck gates are in the
[validation plan](../docs/deck-validation-plan.md); promotion is a separate step in the
[delivery workflow](../docs/community-delivery.md).

## Original reconciled candidate

The current local notice candidate is recorded separately below; the earlier
candidates retain their own inventories and historical notice paths.

The reviewed archive is `ac-deck-linux-x86_64.tar.gz`, 36,369,090 bytes,
SHA-256 `5d08f2f48f43f5e5b1c3580acf0e15d3431ebb2e632d19fc02fdb82e4efbcd39`.
The executable SHA-256 is
`fbbcdae754d1cf3604abdc1559e26721ca38a1189dbdf3d2f5b3a73a9dcf45b7`;
the manifest SHA-256 is
`2201f600a5fb754a6e5da60497d73f16b7b4964a991c9be1f6138c4358f8a759`.
This identifies the existing reconciled working-tree candidate, not a release
commit. These values do not identify a later package with corrected notices.

All 89 ELF-file hashes were independently checked against the candidate and
its build-origin inventory. Coverage is 38 Ubuntu ELF files, six explicit
native inputs, seven Pillow extension modules, 36 wheel-library copies,
one `libpython` and the executable. Identical libraries at `_internal/` and
`_internal/pillow.libs/` count as two distributed files, not two versions.

The local review retained package ownership, installed source-package versions,
original copyright files for 37 Ubuntu binary packages, seven common license
texts, Python distribution metadata and official source descriptors for all
34 Ubuntu source packages. Descriptors were fetched and hashed, not verified
with a signing key. They identify source tarballs and packaging changes; they
are not the complete source archives. Private paths and local receipts are not
prerequisites for contributors following this public review.

## Versioned-cycle candidate

The subsequent `cold-community-posix-01` candidate passed the recorded package
checks. Its archive is 36,369,139 bytes, SHA-256
`851f8e2d9c7d87ad81e53aede854f39d4e7bbd349fff0e05d5b05d309d8ee265`;
the manifest SHA-256 is
`b829c05f325c41baaca80546b2cc01aa81c0caa0311f798dfafbc81c11cde29f`.
Its source inventory SHA-256 is
`3585119a6dc48196a361c4b5e9c4165606899997759e6d4347defad0d09df7ae`.
The source identity remains a frozen working-tree snapshot, not a published
commit. See the [build record](../docs/build-validation.md) for the complete run.

This review independently read the new archive and checked all 89 ELF hashes.
The 88 non-executable ELF files and the executable are byte-identical to the
original reviewed candidate. Origin records retain the same persistent Python
SDK and WSL system-library paths. The six explicit native input copies have
new build-scratch paths and unchanged input names and hashes; this does not
resolve their missing original package/build receipts. The font and all
31 files under `licenses/` also match the original candidate exactly.

The archive carries the revised repository `NOTICE`, SHA-256
`89a07156f31791ba222f57779f7e51df12c8e8fcb3330918b278d631788ca73a`.
Its bytes match the current source notice; the inaccurate statement that
dependency sources already accompany every compiled distribution is removed.
This repository review document itself is not bundled in the runtime archive.

The compiled receipt records 73 product modules loaded from executable
archives and compared with the frozen sources, zero product imports from the
source checkout, and 104 synthetic runtime tests with no skips/failures.
The executable hash remains
`fbbcdae754d1cf3604abdc1559e26721ca38a1189dbdf3d2f5b3a73a9dcf45b7`.
Of the 76 source hashes in `build-info.json`, only the builder script changed;
the runtime source hashes are unchanged. These records support applying the
same dependency review and outstanding gates to these exact new bytes. They
do not deliver sources, add missing notices, establish license compatibility,
test a physical Deck or authorize publication. No review gate below closes
merely because this candidate passed its package checks.

## Source and notice preparation

The subsequent authorized collection acquired and verified all complete
source sets named by the 34 Ubuntu descriptors, six native libraries'
sources/patches/build recipes, 19 standalone Python component source sets,
PyInstaller/hooks, Pillow and identified vendor sources. The 275-file archive
is 450,073,821 bytes, SHA-256
`db611e89f779abec10900537535261fe09ea7529a77f803618aee6b50ed397df`.
The [public inventory](../licenses/dependency-sources.json), SHA-256
`b0fbff02c2d4fb84d7c049dc4233cb7fb276ca12c83b84c19d19233a9f2e137b`,
records exact URLs, sizes, hashes, source requirements and evidence limits.
Proof binary packages/wheels are excluded from this source archive.

The collector uses only public inventory/notices/recipes and HTTPS sources,
then checks every final archive member against the exact embedded inventory.
Its prepared build-notice directory contains 95 files, 1,135,174 bytes, outside
the existing SDK. See [dependency sources](../docs/dependency-sources.md) for independent
reproduction and recipient source-access/replacement instructions. The SDK and
old runtime archives were preserved; local material is not a published offer.

All six native ELF origins now match official Debian/Arch package members.
The Arch PKGBUILD hashes match BUILDINFO and the upstream sources match the
original SHA-512 values. All 43 Pillow ELF copies and the full composite notice
match the pinned official wheel. Wheel Xau matches AlmaLinux 1.0.9-3.el8 through
the original hash in its auditwheel name and matching code/data/build-ID
sections; its exact upstream tar/spec are supplied. Auditwheel rewriting and
the original build cache were not reproduced.

A focused disposable-copy test loaded a different compatible ALSA library,
passed CLI and `SDL_Init(0)`/`SDL_Quit`, and identified its version/mapped bytes.
It did not rebuild the library or test hardware/all ABI behavior. This is
bounded evidence of shared-library replacement, not physical Deck acceptance.

## Candidate with collected notices

The `community-licenses-20261102` archive is 36,544,382 bytes, SHA-256
`0638856a6af365e1481721cd69ac91a51304292e01b2fbc5d4c262594eff2a91`.
Its 195 files carry the 95 collected SDK-input notices, each checked against
the frozen public inventory. The 89 ELF files, including the executable, are
unchanged from `851f8e2d…`; its matching dependency sources are the independently
verified 275-artifact companion, SHA-256
`db611e89f779abec10900537535261fe09ea7529a77f803618aee6b50ed397df`.
The dependency lock explicitly names the reviewed `851f8e2d…` base; byte
comparison establishes its applicability to the identical dependencies here.

Collected notice paths use the collector's namespaces under `licenses/sdk/`,
including `sdk/`, `ubuntu/`, common license texts and static/vendor notices.
The earlier 28 SDK-input paths were replaced by 95 collected paths, a net
increase of 67. Historical path references elsewhere in this review describe
their original candidates. The current source mapping is in
[`dependency-sources.json`](../licenses/dependency-sources.json).

The exact old-to-new notice update and rollback passed in an isolated
installation, with player-data and Steam/CSP fixtures preserved. This verifies
package ownership/recovery, not license compatibility or physical Deck use.
Berkeley DB/PolyForm and the remaining publication gates still require closure.

## Python and build tools

| Component | Exact origin and license evidence | Result |
| --- | --- | --- |
| CPython 3.13.5 | [CPython source and license](https://github.com/python/cpython/tree/v3.13.5); [standalone release 20250612](https://github.com/astral-sh/python-build-standalone/releases/tag/20250612), `cpython-3.13.5+20250612-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz` | The existing original archive matches the official release asset digest `5c63e7ffe47baff0a96a685c94fb5075612817741feb4e85ec3cc082c742b4f8`; its `libpython` exactly matches the candidate (`9c6f83d273b1e1d847f0a2b14230e6e076186d88df22d40cdbaddb2965e46b1b`). PSF/historical notices are bundled. Review embedded dependencies separately. |
| PyInstaller 6.22.3 | [Versioned terms](https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/COPYING.txt) | GPL-2.0-or-later with the bootloader exception for embedded bootloader/loader files; runtime hooks use Apache-2.0. The copied notice includes these terms. This exception does not waive dependency obligations. |
| pyinstaller-hooks-contrib 2026.9 | [Versioned terms](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/v2026.9/LICENSE) | Build hooks are GPL-2.0-or-later; runtime hooks are Apache-2.0. The analysis inventory uses PyInstaller's `inspect`, `pkgutil` and `multiprocessing` runtime hooks and shows no contrib runtime hook. Keep the exact hook inventory with the build. |
| Pillow 12.2.0 | [Release source](https://github.com/python-pillow/Pillow/tree/12.2.0), [PyPI files](https://pypi.org/project/pillow/12.2.0/#files) | MIT-CMU for Pillow; bundled wheel libraries retain their individual terms below. The pinned wheel digest is `eedf4b74eda2b5a4b2b2fb4c006d6295df3bf29e459e198c90ea48e130dc75c3`. The downloaded official wheel independently matches all 43 ELF copies and the full composite notice; complete source and recipes were acquired. |
| altgraph 0.17.5, packaging 26.3, setuptools 84.0.0 | Installed distribution metadata and pinned requirements | MIT, Apache-2.0 OR BSD-2-Clause, and MIT respectively. These build dependencies are not identified as runtime modules in this candidate's analysis inventory. Shipping the SDK itself would require a separate inventory and notices. |

The seven Pillow ELF extensions are `_avif`, `_imaging`, `_imagingcms`,
`_imagingft`, `_imagingmath`, `_imagingtk` and `_webp`, each with the
`.cpython-313-x86_64-linux-gnu.so` suffix under `_internal/PIL/`.

### Embedded Python dependencies

ELF dependencies alone do not inventory statically incorporated code.
`libpython` requires system GLIBC libraries dynamically, but contains built-in
`_dbm`, `_ssl`, `_sqlite3`, `_bz2`, `_lzma`, `_ctypes`, `_tkinter`, curses,
editline and other native modules. Its configuration selects BDB, mimalloc,
LTO and the experimental JIT. Version probes and strings confirm Berkeley DB
**6.0.19**, OpenSSL 3.0.16, SQLite 3.47.1, zlib 1.3.1, Expat 2.6.3 and
ncurses 6.5.20240427. The official
[standalone dependency recipe](https://github.com/astral-sh/python-build-standalone/blob/20250612/pythonbuild/downloads.py)
provides source URLs, versions and checksums for the other components.

| Embedded component | Version/source in that recipe | Terms and review boundary |
| --- | --- | --- |
| Berkeley DB | 6.0.19, `db-6.0.19.tar.gz`, source SHA-256 `2917c28f60903908c2ca4587ded1363b812c4e830a5326aaa77c9879d13ae18e` | **Source acquired; compatibility/access decision remains open.** The exact source archive substantively matches `LICENSE.bdb.txt`; clause 3 requires source information for DB and accompanying software using DB, with redistribution under reasonable conditions. Do not treat this as ordinary BSD permission or assume PolyForm compatibility. |
| OpenSSL | 3.0.16 | Apache-2.0; preserve notices. |
| SQLite | 3.47.1 (`3470100`) | Public domain; record provenance. |
| bzip2; Expat; libffi | 1.0.8; 2.6.3; 3.4.6 | bzip2 license; MIT; MIT. |
| libedit; mpdecimal; ncurses | 20240808-3.1; 4.0.0; 6.5 | BSD-3-Clause; BSD-2-Clause; X11-style terms. |
| liblzma; zlib; libuuid | 5.2.12; 1.3.1; 1.0.3 | liblzma public domain for this version; Zlib; BSD-3-Clause. These are distinct from the newer separately bundled shared libraries. |
| Tcl; Tk; Tix | 8.6.14; 8.6.14; 8.4.3.6 | Tcl/Tk notices; retain exact static-build selection. |
| X11; Xau; XCB | Recipe pins 1.6.12; 1.0.11; 1.17.0 | MIT/X11 notices exist; establish exactly which parts are statically incorporated before claiming complete coverage. |
| mimalloc, HACL*, JIT and other CPython vendor code | CPython v3.13.5 and standalone build recipes | The older root license alone is insufficient. Exact original vendor headers and full [CPython acknowledgements](https://github.com/python/cpython/blob/v3.13.5/Doc/license.rst), including mimalloc, are now in the prepared notice selection. The install-only runtime does not supply a complete linker map. |

[Oracle directs recipients to the LICENSE in the exact DB distribution](https://docs.oracle.com/cd/E17275_01/html/license/license_db.html).
Before publishing this Python binary, review the Sleepycat terms against the
actual combined distribution, provide the required sources and notices, or
prepare a separately reviewed SDK without BDB. Source availability alone does
not establish compatibility with every restriction. Do not modify the existing
SDK or remove a notice to make this gate pass. Oracle's [generic 6.0 announcement](https://oss.oracle.com/pipermail/bdb/2013-June/000056.html)
states AGPL; the exact hash-pinned source acquired here contains Sleepycat
terms. Preserve that discrepancy and the actual bytes rather than using a
version number or announcement alone as a license determination.

## Wheel libraries

Each filename below appears both directly in `_internal/` and under
`_internal/pillow.libs/`; the two copies have matching hashes. The copied
`licenses/sdk/pillow.txt` and `licenses/Pillow-LICENSE` include the wheel's
composite notice. Version evidence comes from the binary, Pillow feature
probes and its versioned
[wheel recipe](https://github.com/python-pillow/Pillow/blob/12.2.0/.github/workflows/wheels-dependencies.sh).
The recipe is provenance evidence, not proof of every cached build input.

| Distributed filename, twice | Component/version | Terms/source review |
| --- | --- | --- |
| `libXau-154567c4.so.6.0.0` | AlmaLinux Xau 1.0.9-3.el8 | Original hash matches auditwheel prefix; code/data/build-ID sections match. Exact source tar/spec and MIT/X11 notice supplied; dynamic metadata rewriting was not reproduced. |
| `libavif-a883386a.so.16.4.1` | libavif 1.4.1 | BSD-2-Clause; complete source/recipe and identified AOM 3.13.2, dav1d 1.5.3, libyuv 6067afde5 and SharpYUV source references supplied with notices. Original cached build was not reproduced. |
| `libbrotlicommon-785b7a00.so.1.2.0` | Brotli 1.2.0 | MIT. |
| `libbrotlidec-08d35d18.so.1.2.0` | Brotli 1.2.0 | MIT. |
| `libfreetype-d2d71ad9.so.6.20.6` | FreeType 2.14.3 | Choose and record FTL, already present in the wheel notice, including the required FreeType acknowledgement; do not silently select its alternative GPL terms. |
| `libharfbuzz-ef65cc8a.so.0.61321.0` | HarfBuzz 13.2.1 | Old MIT; retain per-component notices. |
| `libjpeg-8296d2fa.so.62.4.0` | libjpeg-turbo 3.1.4.1 | IJG, BSD and Zlib terms represented in the wheel notice; retain required acknowledgements. |
| `liblcms2-545f6561.so.2.0.18` | Little CMS 2.18 | MIT. |
| `liblzma-3c942967.so.5.8.3` | XZ/liblzma 5.8.3 | Permissive/public-domain and 0BSD notices as supplied; do not classify the library by the licenses of XZ command-line tools. |
| `libopenjp2-f3576751.so.2.5.4` | OpenJPEG 2.5.4 | BSD-2-Clause. |
| `libpng16-65c953c0.so.16.56.0` | libpng 1.6.56 | libpng notices. |
| `libsharpyuv-0bacc318.so.0.1.2` | SharpYUV, libwebp recipe 1.6.0 | BSD-style libwebp notices; filename is an ABI version. |
| `libtiff-f4bc73ff.so.6.2.0` | libtiff 4.7.1 | libtiff permissive terms. |
| `libwebp-67ee3789.so.7.2.0` | libwebp 1.6.0 | BSD-style terms and patent grant. |
| `libwebpdemux-eeb71312.so.2.0.17` | libwebp 1.6.0 | Same release, demux component. |
| `libwebpmux-20a90b09.so.3.1.2` | libwebp 1.6.0 | Same release, mux component. |
| `libxcb-bac6ebc8.so.1.1.0` | XCB 1.17.0 in the wheel recipe | MIT/X11; retain actual manylinux build inputs. |
| `libzstd-6ea785c0.so.1.5.7` | Zstandard 1.5.7 | Select BSD-3-Clause from the offered alternative terms and preserve the notice. |

The extensions also include Raqm 0.10.3 (MIT) and zlib-ng 2.3.3 (Zlib).
FriBidi 1.0.13 observed in the SDK probe came from the WSL system, not the
archive: the versioned [FriBidi shim](https://github.com/python-pillow/Pillow/blob/12.2.0/src/thirdparty/fribidi-shim/fribidi.c)
loads it dynamically. It is absent from the 89 packaged ELF files. Record this
optional host dependency during Deck checks; do not invent bundled FriBidi
source obligations from a host probe. If it is added to a future package,
its LGPL obligations join that package's review.

## Explicit native inputs and font

| Input | Observed version and notices | Remaining provenance |
| --- | --- | --- |
| `libSDL2-2.0.so.0` | Debian 2.32.4+dfsg-1; original member matches candidate SHA. [Source](https://github.com/libsdl-org/SDL/tree/release-2.32.4). | Exact descriptor, source tar and Debian patches/build material acquired; Zlib and applicable per-file notices retained. |
| `libXss.so.1` | Arch libxss 1.2.5-1; original member matches candidate SHA. [Source](https://gitlab.freedesktop.org/xorg/lib/libxscrnsaver). | PKGBUILD matches BUILDINFO; upstream source matches original SHA-512; MIT/X11 notice retained. |
| `libasound.so.2` | Debian libasound2t64 1.2.14-1; original member matches candidate SHA. [Source](https://www.alsa-project.org/files/pub/lib/). | Exact source descriptor, tar, patches and build material acquired; LGPL-2.1-or-later notice retained. Recipient release access remains pending. |
| `libdecor-0.so.0` | Arch 0.2.5-1; original member matches candidate SHA. [Source](https://gitlab.freedesktop.org/libdecor/libdecor). | PKGBUILD matches BUILDINFO; upstream source matches original SHA-512; MIT notice retained. Unexpected HTTP bodies were rejected. |
| `libmp3lame.so.0` | Debian libmp3lame0 3.100-6+b3; original member matches candidate SHA. [Source](https://lame.sourceforge.io/download.php). | Exact source 3.100-6 descriptor/tar/patches/build material acquired; LGPL-2.0-or-later notice retained. Other tested binary rebuilds did not match. |
| `libsamplerate.so.0` | Arch 0.2.2-3; original member matches candidate SHA. [Source](https://github.com/libsndfile/libsamplerate/tree/0.2.2). | PKGBUILD matches BUILDINFO; source matches original SHA-512; BSD-2-Clause notice retained. |
| `DejaVuSans.ttf` | 2.37; matches the installed Ubuntu `fonts-dejavu-core` 2.37-8 font and its copyright file byte for byte. [Font terms](https://dejavu-fonts.github.io/License.html). | Origin and notice resolved: SHA-256 `ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280`; bundled `dejavu.txt` also matches. Retain Bitstream/DejaVu/Arev terms, naming and standalone-sale conditions. |

The six original transport paths did not establish package provenance and none
matched the installed WSL libraries. Later official package-member matches and
exact source/build records resolve that gap without replacing SDK inputs.

## Ubuntu libraries

All filenames below are under `_internal/`. The version is the **source
package version reported by dpkg for the exact mapped installed library**;
binary ownership and original-file hashes were retained. Source links name
that version, including Ubuntu patches. Broad package copyright files may
also cover tools that are not bundled; a GPL label elsewhere in a package
does not by itself classify the shared library.

| Packaged ELF filename(s) | Exact source package/version | Library terms to carry |
| --- | --- | --- |
| `libFLAC.so.12` | [flac 1.4.3+ds-2.1ubuntu2](https://launchpadlibrarian.net/722072101/flac_1.4.3+ds-2.1ubuntu2.dsc) | BSD-3-Clause for libFLAC; preserve applicable notices |
| `libX11-xcb.so.1`, `libX11.so.6` | [libx11 2:1.8.7-1ubuntu0.1](https://launchpadlibrarian.net/880280233/libx11_1.8.7-1ubuntu0.1.dsc) | MIT/X11 and applicable permissive notices |
| `libXau.so.6` | [libxau 1:1.0.9-1build6](https://launchpadlibrarian.net/723756636/libxau_1.0.9-1build6.dsc) | MIT/X11 |
| `libXcursor.so.1` | [libxcursor 1:1.2.1-1build1](https://launchpadlibrarian.net/723756907/libxcursor_1.2.1-1build1.dsc) | MIT/X11 |
| `libXdmcp.so.6` | [libxdmcp 1:1.1.3-0ubuntu6](https://launchpadlibrarian.net/723756890/libxdmcp_1.1.3-0ubuntu6.dsc) | MIT/X11 |
| `libXext.so.6` | [libxext 2:1.3.4-1build2](https://launchpadlibrarian.net/723756992/libxext_1.3.4-1build2.dsc) | MIT/X11 |
| `libXfixes.so.3` | [libxfixes 1:6.0.0-2build1](https://launchpadlibrarian.net/723756945/libxfixes_6.0.0-2build1.dsc) | MIT/X11 |
| `libXi.so.6` | [libxi 2:1.8.1-1build1](https://launchpadlibrarian.net/723756971/libxi_1.8.1-1build1.dsc) | MIT/X11 |
| `libXrandr.so.2` | [libxrandr 2:1.5.2-2build1](https://launchpadlibrarian.net/723757092/libxrandr_1.5.2-2build1.dsc) | MIT/X11 |
| `libXrender.so.1` | [libxrender 1:0.9.10-1.1build1](https://launchpadlibrarian.net/723757062/libxrender_0.9.10-1.1build1.dsc) | MIT/X11 |
| `libapparmor.so.1` | [apparmor 4.0.1really4.0.1-0ubuntu0.24.04.3](https://launchpadlibrarian.net/740013917/apparmor_4.0.1really4.0.1-0ubuntu0.24.04.3.dsc) | LGPL-2.1-or-later for libapparmor |
| `libasyncns.so.0` | [libasyncns 0.8-6build4](https://launchpadlibrarian.net/723750471/libasyncns_0.8-6build4.dsc) | LGPL-2.1-or-later |
| `libbsd.so.0` | [libbsd 0.12.1-1build1](https://launchpadlibrarian.net/722170993/libbsd_0.12.1-1build1.dsc) | BSD/ISC/MIT and public-domain notices; retain full file |
| `libcap.so.2` | [libcap2 1:2.66-5ubuntu2.4](https://launchpadlibrarian.net/856063469/libcap2_2.66-5ubuntu2.4.dsc) | BSD-3-Clause OR GPL-2.0; record BSD selection |
| `libdbus-1.so.3` | [dbus 1.14.10-4ubuntu4.1](https://launchpadlibrarian.net/742948005/dbus_1.14.10-4ubuntu4.1.dsc) | GPL-2.0-or-later OR AFL-2.1; record/review AFL selection |
| `libexpat.so.1` | [expat 2.6.1-2ubuntu0.6](https://launchpadlibrarian.net/877862227/expat_2.6.1-2ubuntu0.6.dsc) | MIT |
| `libffi.so.8` | [libffi 3.4.6-1build1](https://launchpadlibrarian.net/723752144/libffi_3.4.6-1build1.dsc) | MIT for the library; retain applicable notices |
| `libgbm.so.1` | [mesa 25.2.8-0ubuntu0.24.04.2](https://launchpadlibrarian.net/862086886/mesa_25.2.8-0ubuntu0.24.04.2.dsc) | MIT and applicable permissive notices for libgbm |
| `libgcc_s.so.1`, `libstdc++.so.6` | [gcc-14 14.2.0-4ubuntu2~24.04.1](https://launchpadlibrarian.net/843453090/gcc-14_14.2.0-4ubuntu2~24.04.1.dsc) | GPL-3.0-or-later WITH GCC-exception-3.1 |
| `libgcrypt.so.20` | [libgcrypt20 1.10.3-2ubuntu0.2](https://launchpadlibrarian.net/874716118/libgcrypt20_1.10.3-2ubuntu0.2.dsc) | LGPL-2.1-or-later plus applicable contribution notices |
| `libgpg-error.so.0` | [libgpg-error 1.47-3build2](https://launchpadlibrarian.net/723752569/libgpg-error_1.47-3build2.dsc) | LGPL-2.1-or-later plus permissive notices |
| `liblz4.so.1` | [lz4 1.9.4-1build1.1](https://launchpadlibrarian.net/742948377/lz4_1.9.4-1build1.1.dsc) | BSD-2-Clause for library; record selection |
| `liblzma.so.5` | [xz-utils 5.6.1+really5.4.5-1ubuntu0.4](https://launchpadlibrarian.net/880985790/xz-utils_5.6.1+really5.4.5-1ubuntu0.4.dsc) | liblzma public domain; retain applicable build notices |
| `libmd.so.0` | [libmd 1.1.0-2build1](https://launchpadlibrarian.net/723753477/libmd_1.1.0-2build1.dsc) | BSD/ISC/Beerware/public-domain notices; retain full file |
| `libmpg123.so.0` | [mpg123 1.32.5-1ubuntu1.1](https://launchpadlibrarian.net/757270325/mpg123_1.32.5-1ubuntu1.1.dsc) | LGPL-2.1 |
| `libogg.so.0` | [libogg 1.3.5-3build1](https://launchpadlibrarian.net/723754117/libogg_1.3.5-3build1.dsc) | BSD-3-Clause |
| `libopus.so.0` | [opus 1.4-1build1](https://launchpadlibrarian.net/723760497/opus_1.4-1build1.dsc) | BSD-style and patent terms |
| `libpulse.so.0`, `libpulsecommon-16.1.so` | [pulseaudio 1:16.1+dfsg1-2ubuntu10.1](https://launchpadlibrarian.net/762763897/pulseaudio_16.1+dfsg1-2ubuntu10.1.dsc) | LGPL-2.1-or-later for bundled client/common libraries; check used files |
| `libsndfile.so.1` | [libsndfile 1.2.2-1ubuntu5.24.04.1](https://launchpadlibrarian.net/776244982/libsndfile_1.2.2-1ubuntu5.24.04.1.dsc) | LGPL-2.1-or-later plus applicable permissive notices |
| `libsystemd.so.0` | [systemd 255.4-1ubuntu8.18](https://launchpadlibrarian.net/880850379/systemd_255.4-1ubuntu8.18.dsc) | LGPL-2.1-or-later plus applicable permissive/syscall notices |
| `libvorbis.so.0`, `libvorbisenc.so.2` | [libvorbis 1.3.7-1build3](https://launchpadlibrarian.net/723756472/libvorbis_1.3.7-1build3.dsc) | BSD-3-Clause |
| `libxkbcommon.so.0` | [libxkbcommon 1.6.0-1build1](https://launchpadlibrarian.net/723757009/libxkbcommon_1.6.0-1build1.dsc) | MIT/X11-style and applicable notices |
| `libz.so.1` | [zlib 1:1.3.dfsg-3.1ubuntu2.3](https://launchpadlibrarian.net/882128553/zlib_1.3.dfsg-3.1ubuntu2.3.dsc) | Zlib |
| `libzstd.so.1` | [libzstd 1.5.5+dfsg2-2build1.1](https://launchpadlibrarian.net/742948371/libzstd_1.5.5+dfsg2-2build1.1.dsc) | BSD-3-Clause OR GPL-2.0; record BSD selection |

The two runtime archives recorded above do not contain these 37 complete package notices or the
referenced `/usr/share/common-licenses` texts as a complete reviewed set.
Some Python SDK notices cover differently built versions of similarly named
libraries and cannot establish coverage for these bytes. The review collected
the original notices into the public 95-file selection; integrate it into a new
candidate rather than editing this candidate or its successful manifest.

## Corresponding sources and replacement

For the distributed LGPL libraries, preserve the applicable copyright/license
notices, provide complete corresponding library sources with used patches and
build/install scripts, and document a usable replacement mechanism. Merely
linking a current upstream homepage or an earlier preview's source archive
does not identify the source of these binaries. LGPL-2.1 sections 4 and 6
distinguish distributing the library from distributing the combination and
require rights for modification and reverse engineering for debugging those
modifications. See the [license text](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html),
also [retained in systemd's source](https://github.com/systemd/systemd/blob/v255/LICENSE.LGPL2.1).

At minimum this applies to ALSA, LAME, libapparmor, libasyncns, libgcrypt,
libgpg-error, libmpg123, libpulse/libpulsecommon, libsndfile and libsystemd,
with each library's exact version of LGPL. Retain the other permissive
notices contained in those source packages. D-Bus offers GPL-2.0-or-later or
AFL-2.1: record the selected AFL route and its source-access, notice and
recipient conditions, or evaluate the GPL route before distribution. Do not
assume it is MIT.

The bundled GCC runtime libraries use GPL-3.0-or-later with the
[GCC Runtime Library Exception 3.1](https://github.com/gcc-mirror/gcc/blob/releases/gcc-14.2.0/COPYING.RUNTIME).
The exception permits eligible combinations; it does not remove the license
or corresponding-source review for the redistributed library files themselves.
Include their exact Ubuntu source and exception notices in the release plan.

Use the official source descriptor for each Ubuntu version to obtain the
listed upstream and Debian/Ubuntu source files; verify their SHA-256 values,
retain the descriptors and patches, and provide equivalent access alongside
the runtime. The collector now acquired all complete listed source sets and verified their
sizes/digests, rather than descriptors alone. Berkeley DB
needs a separate closure decision as described above. The earlier preview's
dependency sources have not been accepted as sources for this candidate.

Before marking replacement support complete, test on a disposable extracted
copy that a recipient can substitute an interface-compatible rebuilt LGPL
library and run the packaged CLI. Document filenames, SONAME/ABI expectations
and library search behavior. If a component is statically combined, provide
the required relinkable material and instructions under the selected terms.
Existing informational CLI/relocation checks are not a replacement test.

The original reconciled candidate's `NOTICE` acknowledges LGPL rights but
generically says sources accompany the compiled distribution. That statement
is not true of that local archive by itself. The repository's revised `NOTICE`,
carried by the versioned-cycle candidate, requires verification for each exact
distribution. Recipient release access to prepared material is still required. Do not use
either notice as proof of source delivery. Project-owned PolyForm terms must
not override recipients' applicable dependency rights.

## Code, gallery and external content

The candidate carries the AGA MIT notice in `THIRD_PARTY_NOTICES.md` and the
ACC DualSense Feedback attribution in its notices. These cover the stated
code integration, not game artwork or voices. The community payload boundary
excludes game/DLCs, Steam, Proton prefixes, CSP, private camera archives, album
images and Toasty image/audio files. Exported feature code and filenames do
not redistribute those excluded files. Short translated quotations embedded
in `rogue_rewards.py` still require a recorded translation/source-rights
decision; do not infer it from the author's age alone.

The ten repository gallery images have their own source/hash manifest and
acknowledge the supplied Assetto Corsa, Nissan and Spa previews. Attribution
and user-supplied inputs do not establish a redistribution grant. Record an
applicable permission/terms decision for those exact images or replace the
artwork with material whose rights are established. The gallery is not in
this runtime archive; its publication gate remains separate.

The installer downloads pinned CSP 0.3.1 separately for the player's setup.
That is distinct from mirroring or bundling it. Keep the official download,
hash checks and preparation boundary; runtime compatibility still needs Deck
testing. No CSP redistribution grant was established, so an installer check
does not authorize adding CSP bytes to a public release. Optional camera
adapters use the player's verified original scripts and remain subject to
their separate rights review. See the [integration inventory](../docs/third-party-integrations.md).

## Publication blockers and minimum closure

| Gate | Current status | Minimum action before claiming closure |
| --- | --- | --- |
| Exact ELF inventory | Resolved for this candidate | Retain the 89-file hashes/origins; repeat for changed bytes. |
| Python archive and font origin | Resolved | Retain the official standalone archive match and font/package/notice match. |
| Six native input origins | Resolved | Retain the six official package matches and exact source/build records; repeat for changed bytes. |
| Berkeley DB and Python statics | Sources/notices prepared; compatibility decision open | Decide the Sleepycat distribution route or separately review Python without BDB; preserve the exact source/notice evidence and provide matching application source access. |
| Wheel vendor provenance | Official wheel and identified vendor origins checked | Retain exact wheel/full notices, vendor sources and recipes. Original build cache/auditwheel recreation remains a reproducibility limit. |
| Ubuntu notices | Public 95-file selection integrated and verified in the new local candidate | Preserve the matching source inventory and applicable D-Bus AFL recipient terms when preparing recipient access. |
| Corresponding source delivery | Complete reviewed source material verified locally; release access pending | Provide the exact 275-file archive/checksum, matching application sources and equivalent recipient access alongside the approved runtime. |
| Replacement/relink rights | Focused shared-library replacement passed; instructions prepared | Supply accurate rights/instructions and source/build material; keep the one-library proof separate from all ABI/hardware claims. |
| Gallery and quotations | Open for publication | Record rights decisions for the supplied gallery artwork and exact embedded translations, or replace/exclude affected material. |
| CSP distribution boundary | Exclusion verified by candidate inventory; runtime test open | Keep CSP external; obtain a grant before any proposed mirroring/bundling. Test the separately downloaded kit on Deck. |
| Release source/notice truthfulness | Open | Match published sources to the immutable candidate, correct source-access statements, and repeat package checks after any input changes. |

Source material was acquired without executing it. This review did not replace
the SDK, mutate old runtime packages, publish Git or operate a physical Deck. A corrected notice or
runtime input produces a different candidate and requires its own hashes and
package checks.
