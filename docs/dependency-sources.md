# Dependency sources and notices

Download the matching source companion and checksums from
[v0.1.0-preview.1](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1).
The source tag supplies corresponding ac-deck application code. No private
repository, developer account or paid download is needed for this release
material. Installing the launcher does not require building it.

| Material | Identity |
| --- | --- |
| `ac-deck-dependency-sources.tar.gz` | 385919586 bytes; SHA-256 `77a296984f0d07c5239f29630e44e7594a19899d56258a56c046f503fd260889` |
| [Pinned inventory](../licenses/dependency-sources.json) | SHA-256 `05d9cc8128641eee1ee819fd959c84c8e2444fe09f02f63be1da2a42f1487023`; 67 components and 252 files |
| Dependency notices | 84 original files under `licenses/dependency-notices/`, copied into runtime `licenses/sdk/` |

The [current review](dependency-license-review.md) records the license routes
and exact runtime identity. Older 275-file/95-notice material belongs to the
[historical review](../archive/dependency-license-review-20261102.md), not this
new interpreter's source companion.

## Collect and verify

Use Python 3.10 or newer from a public Linux checkout, with independent regular
files on a Linux filesystem. The collector needs neither a build SDK nor a
private package database. Remote inputs have pinned HTTPS URLs, sizes and
SHA-256 values; repository notices and recipes retain original bytes.
From the repository root:

```sh
python3 -B scripts/preparar_fontes_dependencias.py \
  --manifest licenses/dependency-sources.json \
  --output local/dependency-sources/collection
```

An existing file is reused only when its size and hash match. Divergent files,
symlinks, unsafe paths, non-HTTPS redirects and mismatched bytes are refused
and preserved. Failed downloads do not replace verified artifacts. Do not
remove inventory entries or relax filesystem checks to bypass a failure.

Verify without network access, then create a new companion archive:

```sh
python3 -B scripts/preparar_fontes_dependencias.py \
  --manifest licenses/dependency-sources.json \
  --output local/dependency-sources/collection --verify-only
python3 -B scripts/preparar_fontes_dependencias.py \
  --manifest licenses/dependency-sources.json \
  --output local/dependency-sources/collection --verify-only \
  --archive local/dependency-sources/ac-deck-dependency-sources.tar.gz
```

The collector embeds the exact inventory and verifies every archive member's
name, type, size and hash. Added, missing, duplicate or changed members fail.
It never overwrites an existing archive or executes downloaded source/build
scripts. The companion contains source, notices and recipes, not proof binary
packages, wheels, a game or the SDK. Keep this large archive out of Git.

## Included source material

| Group | Material and limit |
| --- | --- |
| Ubuntu libraries | Every member of the exact source descriptors, including originals, packaging, patches and build/install material. Digests checked; detached signatures not verified. |
| Six native inputs | Recorded Debian/Arch origins and exact SDL2, ALSA, LAME, Xss, libdecor and libsamplerate sources/build recipes; package-member and Arch BUILDINFO/PKGBUILD evidence retained. |
| New Python interpreter | CPython 3.13.5 and the six pinned OpenSSL/zlib/bzip2/liblzma/libffi/SQLite sources, versioned SDK recipe, PSF/vendor notices and change summary. Berkeley DB, GDBM and the previous standalone interpreter are excluded from this runtime route. |
| PyInstaller and hooks | Official 6.22.3 and 2026.9 sources and their distinct bootloader, build-hook and runtime-hook terms. |
| Pillow and vendors | Pillow 12.2.0, identified vendor sources/recipes and full wheel notice. The pinned official wheel establishes payload provenance; its original cache and auditwheel rewriting were not recreated. |
| Wheel Xau | AlmaLinux upstream tar/spec and recorded original-hash/section/build-ID comparison. Source RPM binary evidence is not redistributed as source. |

Required corresponding-source material covers the supplied LGPL libraries and
GCC runtime licenses/exception, plus D-Bus source access under AFL-2.1.
Permissive-library sources also preserve provenance; inclusion does not invent
copyleft obligations. FTL is selected for FreeType and BSD-3-Clause for
Zstandard, with original notices intact.

## Use the selected notices

Configure the collection's `notices/` directory as `sdk.licenses`, or pass it
through `--licenses-dir` to the community builder. Keep interpreter, native
libraries, font and reviewed SDK inventory explicit and persistent. Collection
does not install an SDK or replace a player's Steam/Proton setup.

Build and verify a new candidate when an input changes. Do not edit a successful
runtime archive or its manifest to insert notices. Provide the exact companion
and checksum, matching application sources, original notices and these
instructions alongside the runtime. A local path or an older preview's archive
does not supply equivalent source access for new bytes.

## Replacing a library

Applicable LGPL recipients may modify or replace the supplied shared libraries
for their own use and reverse engineer the combination to debug those changes.
Keep the full licenses, copyrights, exact library sources, patches and
build/install scripts; see [LGPL 2.1 sections 4 and 6](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html).
Project-owned purpose restrictions do not supersede these rights.

For Debian/Ubuntu sources, use the exact descriptor and members with
`dpkg-source -x /path/to/package.dsc /new/build/directory` in a separate build
environment. Its `debian/rules`, patches and dependencies describe the package
build. Arch inputs retain PKGBUILD and BUILDINFO evidence. Do not build against
the player's game or overwrite the reviewed production SDK.

Work on a separate extracted runtime copy. Retain the original package and
player data; build or obtain an interface-compatible shared library with the
same SONAME and required symbols, then replace only its corresponding
`_internal/` file in that copy. Record both hashes, run informational CLI first,
and check the needed functions and actual mapped file identity. The player
explicitly starts any window, hardware or game test.

The ALSA replacement proof exercises CLI, `SDL_Init(0)`/`SDL_Quit`, version and
mapped-byte checks; it does not cover every ABI/hardware path. Its exact
candidate and replacement belong to the [build record](build-validation.md).
Normal update integrity checks may refuse a modified installation; preserve
the modified copy and follow [update/recovery](update-and-recovery.md) rather
than suppressing those checks.
