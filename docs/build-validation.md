# Community candidate validation

## Community candidate from Deck build 117

The experimental community package `v0.1.0-preview.3` brings Speed Chase,
Rogue difficulty and objectives, the revised victory screen, Race Synthetizer
and help in Settings. The public installer and its pinned external CSP 0.3.1
download are preserved. Optional victory tracks, album art, Toasty media
and mod archives are excluded. Rogue still shows its objectives and progress
without the optional media.

The source export records the canonical build 117 source revision and the
curated file hashes in the [public manifest](../public-source-manifest.json).
The community version keeps the existing installer and allows saved schema 1
race proposals to use the default AI level when that field is absent.

- 216 public source tests and 139 compiled tests passed without skips.
  Two process fixtures remain source-only. Nine informational CLI checks,
  the bootstrap, relocation with spaces and ten offscreen compositions passed.
- Runtime SHA-256 `813fba0308aee063318ef5e3c87d9323a170e3464ba39b8aa32aefb788aff9d2`.
  The 135 ELF files require at most GLIBC 2.38. All 134 dependency ELFs
  match preview 2 byte for byte. The source companion contains the 278
  materials and the updated inventory. The ALSA replacement check passed
  against a disposable copy of this runtime.
- The [security review](security-review.md#preview-3-advisory-recheck) covers
  the exact package pins and the SteamOS certificate prerequisite.

Use SteamOS 3.9.5 or newer on the Stable channel with the updated system
certificate store. Installation, controls and racing on a physical Deck
remain unverified for this community package. The supported installation
path starts with a fresh runtime. The packaging updater cannot migrate
progress between preview 2 and preview 3.

## Security-corrected preview 2: 3 November 2026

Version **v0.1.0-preview.2** uses the versioned community cycle with a
separate reviewed no-BDB/GDBM SDK, Pillow 13.0.0 and setuptools 84.1.0.
The six exact locked Python packages have no matching current GitHub-reviewed
advisories; the query's positive controls reproduce the 55 old-pin alerts.
Read the [security review](security-review.md) for scope and OS trust limits.
This does not establish that every native dependency has no vulnerability.

- Runtime: 46218949 bytes, SHA-256 `72c1124a647fad0f7d03a1612aac6d9bda5deebd0e172ad9a6e541c1e851d28f`.
- Executable SHA-256: `6dfa64afe517b77adbe5c75ef8e04d907b42beb611535fef38570ae576a2e281`.
- Manifest SHA-256: `24c9ce8516a00b1cb2c4e95689733798fa63c2fb9a4a3bc293e7f6d5b5e32eff`.
- Frozen inputs: 117 files, including 112 selected canonical exports.
- 207 public source tests and 130 compiled tests passed without failures or
  skips. Two explicitly named process fixtures run in the source suite only;
  the compiled subprocess/network/device guard remains enforced.
- Bootstrap, nine informational CLIs, relocation with spaces, actual archived
  code correspondence and ten offscreen compositions passed. No source fallback.
- 135 mapped ELF files, GLIBC maximum 2.38, 103 SDK notices.
- Dependency companion: 278 materials, 69
  components, 389623637 bytes; SHA-256 `89bebd9e5ec368b4cd5f482a83c9ad5b5720029aef3bbd4bfeaf6f95860515a0`.
- The new SDK has 12,388 inventoried entries; manifest SHA-256
  `8e7eb0ff335ab9b0d92d9d846203afbee833a8eead8e895b66236d77f19c2941`.
- Canonical Linux suite: 3,158 tests, no failures/errors, 45 skips (40 Lua,
  four Node classes, one SDL discovery). Packaged SDL is checked explicitly.
- Cycle wall time: 243.647 s. PyInstaller: 13.134 s; tar/gzip: 13.348 s.
  Stage scopes overlap; these are not additive independent measurements.

The [release record](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.2)
binds matching committed source, bootstrap, dependency material and checksums.
The disclaimer/terminal acknowledgement and automated installation fixtures
passed. No real Steam, game, race, microphone or paid API was exercised.
**Physical Deck installation, play, performance and acceptance remain untested.**
The records below retain their original historical identities and limits.

## Withdrawn preview 1: historical validation, 3 November 2026

**Withdrawn for dependency security corrections. Do not install this archive.**

Version **v0.1.0-preview.1** uses the versioned community cycle with the
separate CPython SDK built without Berkeley DB/GDBM. The old SDK and candidates
were preserved. The cycle records a 117-file frozen working tree, derived from
112 selected exports, three policy notices and two provenance inventories.
The source tag and promotion record bind the final public commit to these bytes.

- Archive: 45773729 bytes, SHA-256 `f6e0b14ca8480217793d619bc7d6edb31a2666f486262681cecf301b79fbefb1`.
- Executable SHA-256: `357309498277ddf88c2163231d5c0bfe426fb7628c895ffeca1e010e5f4201db`.
- Manifest SHA-256: `5df8d203d75c865aeb546c5288288a00e52e9c0384f4b0a41ddb34d4ba6ab126`.
- 207 source tests passed without skips; 130 compiled tests passed without skips.
  The two named process fixtures run in the source suite only and are explicit
  in `compiled.json`; the compiled guard remains unchanged.
- Actual archived CodeType matched the frozen runtime sources, with no product
  imports from source. Bootstrap, informational CLI, relocation and ten offscreen
  compositions passed. The runtime carries 136 ELF files and 84 SDK notices;
  highest required GLIBC is 2.38.
- Canonical Linux suite: 3158 tests, no failures/errors, 45 skips (40 Lua,
  four Node classes, one SDL discovery). The export revalidation passed 18
  tests. Packaged offscreen SDL is checked separately with the explicit library.
- SDK: Python 3.13.5, PyInstaller 6.22.3, hooks 2026.9, Pillow 12.2.0;
  12,388 entries, manifest SHA-256
  `f0448385dcb9af1b9ecea7f4181d8d0c5e4ec21e5224c220d0134f8ea464b151`.
  Source-built Python and six static dependencies, original notices and recipe
  are identified in the dependency inventory. Old standalone BDB evidence is historical.

The preview provides a public one-command install with an explicit terminal
disclaimer acknowledgement, Steam-library/account discovery, official CSP
download, compatible-file reuse, missing-file repair and recoverable setup.
First player-started Steam Play can initialize missing default Proton folders
without starting a race. Tests use synthetic fixtures; no real game/Steam,
Deck, microphone or paid API was exercised. Physical support and acceptance
remain unverified.

See [installation](installation.md), [dependency review](dependency-license-review.md)
and [the release evidence](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1).
The records below retain their historical candidate identities.


## Dependency notices and public update: 2 November 2026

The local `community-licenses-20261102` cycle used the unchanged persistent
SDK with the 95 notices produced by the verified public dependency collector.
The 115-file source snapshot contains 110 selected exports, three policy
notices and two provenance inventories. Its base is the public checkout HEAD
`98a53a1865f376b37c87b84b87ea26ac219ae110`; the build identifies working-tree
bytes rather than attributing these changes to that commit.

Handoff: `local/community-license-candidate-20261102/`. Runtime archive:
**36,544,382 bytes**, SHA-256
`0638856a6af365e1481721cd69ac91a51304292e01b2fbc5d4c262594eff2a91`.
Manifest SHA-256:
`a7d48202207ff76f878262bfb4ced72b10ec99c14a941a50c397de8d3f338daf`.
The executable and all 89 ELF files remain identical to the preceding reviewed
runtime. Executable SHA-256:
`fbbcdae754d1cf3604abdc1559e26721ca38a1189dbdf3d2f5b3a73a9dcf45b7`.

| Check | Result |
| --- | --- |
| Source and compiled behavior | 165 source tests and 104 archived runtime tests passed, no skips; zero source fallback |
| Package and resources | 195 files, 95 SDK-input notices with exact collected bytes; bootstrap, relocation with spaces, nine informational CLI runs and ten offscreen images passed |
| ELF | 89 checked; maximum required GLIBC 2.38 |
| Dependency-source companion | 275 artifacts plus exact inventory independently streamed and verified; 450,073,821 bytes, SHA-256 `db611e89f779abec10900537535261fe09ea7529a77f803618aee6b50ed397df` |
| Public updater | Cold public-only fixture, Python 3.12.3: 17 CLI commands covered interruption after an observed effect, resume, missing receipt, unchanged resume, rollback and eight safe refusals |
| New notice package | Actual `851f8e2d…` to `0638856a…` update and rollback passed; 95 paths added, 28 removed, net increase 67; player/CSP/Steam fixtures preserved |
| Shared-library replacement | An isolated ALSA replacement loaded from the package path; CLI and SDL_Init(0) passed. This was not a source rebuild or hardware test. |

PyInstaller took **8.991 s**, tar/gzip **26.591 s**, source-test subprocess
**5.862 s** and archive validation **1.129 s**. Input checks took approximately
15–16 seconds each with the larger notice selection on the Windows-mounted
filesystem. Stage totals include postflight and have overlapping scopes;
they are not compiler-only measurements.

The [update procedure](update-and-recovery.md) is limited to unchanged product
source/Python/data-layout identities. A general functional upgrade or data
migration remains outside it. The full private source suite passed 3,116 tests
with 44 known Lua/Node skips; the public selection passed 165 without skips.

The [source material](dependency-sources.md) and notices are prepared locally.
Berkeley DB/PolyForm compatibility, recipient source access, matching published
first-party sources, media rights, explicit publication approval and physical
Deck use remain separate gates. No original SDK bytes, old packages, Git
staging/commits or player installations were changed by the checks.

## Versioned community cycle: 2 November 2026

An independent execution reproduced a candidate using only a fresh public
copy, the [documented controller](community-delivery.md) and the configured
persistent SDK. No ignored per-candidate build/validation helper was used.
The copy had 139 public files, no Git metadata and a frozen 111-file input
selection: 106 exports, three policy notices and two provenance inventories.
Its local source base is null; canonical provenance remains in the export
manifest. These are identified working-tree bytes, not committed release bytes.

The handoff is `local/community-cycle-candidate-20261102/`, with the archive,
`SHA256SUMS`, `candidate-summary.json`, `source-inventory.json` and `validation/`.
Archive: **36,369,139 bytes**, SHA-256
`851f8e2d9c7d87ad81e53aede854f39d4e7bbd349fff0e05d5b05d309d8ee265`.
Manifest SHA-256:
`b829c05f325c41baaca80546b2cc01aa81c0caa0311f798dfafbc81c11cde29f`.
The executable remains byte-identical to the prior reconciled candidate:
`fbbcdae754d1cf3604abdc1559e26721ca38a1189dbdf3d2f5b3a73a9dcf45b7`.
The new archive carries the corrected `NOTICE`; publication gates remain open.

| Check | Observed result |
| --- | --- |
| Public source tests | 134 passed, no failures/skips |
| Archived runtime | 104 synthetic tests passed, no failures/skips; 73 archived code entries compared with source and 73 product modules loaded from the executable archive, zero source fallback |
| Package | 128 regular files, exact archive/manifest bytes and POSIX modes, no private payload |
| ELF | 89 files; 88 non-executable libraries unchanged from the reviewed earlier candidate; maximum required GLIBC 2.38, within the 2.39 limit |
| CLI/bootstrap | Nine informational CLI runs; bootstrap checksum, extraction and executable identity passed without running setup |
| Relocation/resources | Path with spaces, packaged SDL/font and ten offscreen images at the two supported resolutions passed |
| Recovery | Controlled snapshot failure retained its attempt/log/blocker; documented resume completed without changing inputs |
| Reuse | A further resume reused all six stages, with byte-identical state and no repeated tests or build |
| Preservation | All 139 public/fixture files, complete SDK inputs, Git HEAD/refs/index and the prior candidate matched before/after |

The first real run found a WSL boundary: extracting under a Windows checkout
changed 0644/0755 to 0777. It correctly failed validation. Runtime validation
artifacts now use the configured Linux work area; logs and receipts can remain
in the checkout. Preflight rejects an unsupported work filesystem. The failed
run and its build were preserved, and the final run used a new cycle after
the reviewed code change. Mode checks were not relaxed.

| Measurement | Seconds |
| --- | ---: |
| Source-test subprocess | 1.789 |
| PyInstaller compilation | 8.405 |
| tar/gzip creation | 26.511 |
| Archive validation | 0.983 |
| Compiled synthetic tests | 0.778 |
| Offscreen composition | 1.122 |
| Successful recovered resume, wall time | 142.055 |
| Unchanged resume with six verified reuses | 50.656 |

The recovered-resume wall time excludes the preceding doctor, plan and
controlled failed attempt. Each source/SDK/environment inventory check took
about eight to nine seconds; unchanged resume still verifies those inputs and
artifacts. The measurements are different scopes and must not be added as if
each were an independent part of the compiler. The observed waits include
inventory checks and compression; compiler time alone is not the cycle time.

No commit, staging, push, release publication, Steam/game operation or physical
Deck test occurred. Follow the [dependency review](dependency-license-review.md),
[Deck plan](deck-validation-plan.md), supported update/recovery gates and
explicit [promotion approval](community-delivery.md#version-and-promotion).

## Reconciled local candidate, 2 November 2026

The reconciled candidate is `local/community-reconciled-candidate-20261102/`. It was
built with the persistent SDK from an independent 100-file snapshot on the
WSL Linux filesystem: the 95 reconciled exports, three public policy notices
and two provenance inventories. The 76 builder inputs match that snapshot and
the selected canonical sources. The canonical Git base is
`60bf9de196a7ccc27b5019c43370c3d309c451cf`; these are **working-tree bytes**,
not a build attributed to that commit alone. The earlier installer candidate
below was preserved.

Archive: `ac-deck-linux-x86_64.tar.gz`, **36,369,090 bytes**.
SHA-256:
`5d08f2f48f43f5e5b1c3580acf0e15d3431ebb2e632d19fc02fdb82e4efbcd39`.
The executable SHA-256 is
`fbbcdae754d1cf3604abdc1559e26721ca38a1189dbdf3d2f5b3a73a9dcf45b7`.

| Check | Result |
| --- | --- |
| Frozen snapshot source selection | 122 tests passed; no failures or skips |
| Archived runtime behavior | 104 synthetic tests passed; no failures or skips; installer/download/discovery, Steam edit/restore, CSP migration, file safety, configuration/session contracts and Rogue persistence |
| Source correspondence | 73 archived code entries compared with the snapshot; all 73 loaded product modules came from the actual executable archive; source fallback refused |
| Actual executable CLI | 12 successful checks: help with a fresh user cache and repeated help, install help and restore help, before extraction, after bootstrap and after renaming the installed folder |
| Actual bootstrap | Verified the archive checksum, extracted to a new path with spaces, retained executable mode and matched every installed file; no `--run-setup` |
| Resources and composition | Ten software-surface images: five views at 1280 × 800 and 1920 × 1200, using the relocated bundle's SDL2 and UI font; no window |
| Package inventory | 128 files, including 127 hashed manifest rows; no missing or additional files, links, CSP/mod/private media, game/DLC, Steam, credentials or player data |
| ELF dependencies | 89 ELF paths checked with readelf/ldd and mapped to technical origins; maximum required GLIBC 2.38, within the 2.39 limit |
| Notices and SDK | Three public notices and 28 preliminary SDK notices retained byte for byte; six selected native libraries, font and the persistent Python SDK manifest checked before/after |

The archived runtime tests execute the actual PyInstaller CodeType objects
under the matching SDK with an import loader that rejects runtime source
fallback. They are distinct from the actual executable/bootloader CLI checks.
The software composition selects the bundled SDL2 explicitly and uses the
bundle's library search path. These checks do not establish a physical Deck
installation, Steam account persistence, a race, performance, offline operation
or full game-data portability.

SDK: CPython 3.13.5, PyInstaller 6.22.3, hooks 2026.9, Pillow 12.2.0,
SDL2 2.32.4, WSL Linux x86_64 and build glibc 2.39. No SDK download,
installation or version change was needed.

| Measured stage | Duration |
| --- | --- |
| Input verification and independent snapshot | 20.153 s |
| Source tests | 1.706 s unittest; 2.193 s process |
| PyInstaller process | 12.091 s |
| tar/gzip packaging | 28.371 s |
| Complete builder, including PyInstaller and packaging | 41.051 s |
| Archived runtime tests | 0.876 s |
| Ten offscreen compositions | 1.196 s |

Nested timings must not be summed. CLI/bootstrap stage durations were not
retained, so no complete elapsed-time claim is made. Failed local validator
attempts are retained: they exposed the private verifier's required `papao`
name, overly strict subprocess guards during SDL discovery, a missing bundle
library search path in the archive probe and a tuple/list comparison after
JSON loading. Only local validation helpers changed; the package was built
once. Completed checks were reused with matching hashes during consolidation.

The candidate directory contains `source-snapshot.json`, `sdk-inputs.json`,
`validation.json`, `elf-dependencies.json`, `elf-origins.json`, PyInstaller TOCs,
source/compiled logs, images, timing receipts and `SHA256SUMS`. Technical ELF
origins cover six explicit native inputs, 44 Python SDK entries, 38 WSL system
libraries selected by PyInstaller and the generated executable. This mapping
does not approve notice coverage or corresponding-source obligations; those
remain a publication gate. No commit, staging, push, publication, delivery
application, real game setup, Steam, race, microphone or paid API occurred.

## Reconciled local source, 2 November 2026

The canonical development source and this distribution now share the selected
launcher, installer/bootstrap and builder implementation, including the newer
Rogue skip/menu behavior. The working-tree [source manifest](../public-source-manifest.json)
records 95 exact files and their canonical source paths. The
[community inventory](../community-changes-manifest.json) preserves the eight
original deltas and identifies their absorption; the Git base alone does not
identify these uncommitted bytes.

The complete public selection passed **122 tests in 3.690 seconds** with the
persistent WSL Linux x86_64 CPython 3.13.5 SDK. Process time including discovery
was 5.369 seconds. No failures or skips. The selected source hashes matched
before/after testing and matched the canonical source. Tests use synthetic
fixtures and do not compile the product, configure a real Steam account or
establish physical Deck behavior. The private export checks and broader tests
are recorded separately in the development handoff.

No product build or publication was performed during that source reconciliation.
The new local candidate above was produced later. The older candidate below
retains evidence only for its own snapshot. SDK notice coverage remains preliminary.

## Local installer candidate, 2 November 2026

The local candidate at `local/community-installer-candidate-20261102/` was
compiled from a 97-file snapshot of the current working tree; the candidate's
`source-snapshot.json` records its exact source hashes. The snapshot public
test selection passed **121 tests in 1.404 seconds** on WSL Linux x86_64 with
Python 3.13.5. The build used PyInstaller 6.22.3, hooks 2026.9, Pillow 12.2.0
and glibc 2.39; the highest required GLIBC symbol recorded was 2.38.

The archive SHA-256 is
`0f3dd6895e938a80dc4e79a20979e29608dee934aadfd0797076a39225990a31`.
All 127 entries in its bundle manifest matched, with no unlisted files. CSP,
camera mods and private media were absent. The bootstrap verified and extracted
the archive to a temporary path containing spaces; the packaged `--help`,
`install --help` and `restore-steam --help` passed. PyInstaller inspection
confirmed the four installer modules are present. No Steam client, game, race,
or launcher window was opened.

This is a local candidate, not a published release. Its 28 selected SDK notice
files are preliminary: coverage for the exact compiled dependencies and the
corresponding source obligations remain to be reviewed. Installation and Steam
configuration have not been exercised on a physical Deck. The snapshot test
time is measured; separate build and packaging durations were not recorded.
The snapshot starts from the export based on private revision `5daf0c8` plus
its then-uncommitted Rogue changes and the local community installer changes.
At the time of this candidate, the private project advanced to `60bf9de` and
the trees had not yet been reconciled. The source reconciliation above happened
later and does not change this candidate. In particular, later Rogue skip changes in the
private tree are not established in this candidate. At that point, the installer
modules, launcher entrypoints and CSP update still needed reconciliation with
the primary project. The later source reconciliation addressed those sources;
it does not change this older binary.

## Earlier community candidate

The local candidate community-preview-002 was built from public source revision
27a9bf1cb05904490f36481ee491d9b6ef88ccae. The manifest at that revision
identified the private source origin as 498812dca4d3e21f4c2624b099278402ba3ed854;
the recorded source hashes matched both trees. The [current source inventory](../public-source-manifest.json)
describes a later export. The results below apply to the earlier candidate, not
to a build from the current source.

The later export records base revision `5daf0c8f5db3789d288e8572f087c645121995b3`
and includes uncommitted source changes from that working tree. Its manifest
records the exported file hashes; the base revision alone does not identify
those bytes. The public test selection passed with Python 3.11.7 on Windows;
the documented Python 3.13.5 build environment and a new compiled package were
not validated in this synchronization.

An additional selection of 70 tests from the development tree did not pass on
Windows: three session tests produced four errors at the Linux-only launch
guard, one Gamepad FX test failed before its Lua fixture ran because the
installed MiKTeX interpreter could not access its configuration, and one Lua
test was skipped. A subsequent WSL run of the proximity preferences and
Gamepad FX selections passed 14 tests and skipped the Lua bridge test because
Lua was unavailable. That bridge test still requires a suitable Lua environment.
Source is available in this repository under [PolyForm Noncommercial
1.0.0](../LICENSE). This report records the original local candidate. An [experimental assembled
preview](https://github.com/alexandrefortes/ac-deck/tree/community-preview-001)
is now public, with first-party license and notice, third-party notices and
corresponding dependency sources. Physical Steam Deck validation remains
separate. The archive hash below identifies the original local candidate; the
published preview has its own checksum in the preview branch.

| Check | Result |
| --- | --- |
| Public source tests | 62 passed, no failures or skips |
| Compiled runtime tests | 62 passed, no runtime source fallback |
| Informational CLI | Help passed from an unrelated directory, cold and warm |
| Relocation | Passed with spaces in the folder name |
| Installed-game attachment | Passed using authored temporary fixtures; no game was started or copied |
| UI composition | Five screens rendered at 1280 × 800 and 1920 × 1200 |
| Distribution inventory | 166 files; no bundled CSP, mods, private media, game or player data |
| Runtime compatibility | Linux x86_64, highest required GLIBC symbol 2.39 |
| SDK notices | 50 exact notice files, with selected-library copyright and referenced license texts |

SDK: Python 3.13.5, PyInstaller 6.22.3, hooks 2026.9 and Pillow 12.2.0.
The archive SHA-256 is
8db2adab138b28fee5013d78a09b4f5662706870998bc8b37bd1cfe8e2cfd7a3.

Completing notices did not change the executable or shared libraries. Standard
library ZIP entries also remained identical; only ZIP container metadata changed.
The final inventory, source hashes, notices and CLI were verified again.

No Steam, launcher window, race, physical microphone or paid API was opened.
These checks do not establish physical Steam Deck behavior, minimum FPS,
offline operation or complete game-data portability. The first-party license
choice is resolved; the dependencies retain their own terms. The experimental
package and corresponding dependency sources are published; hardware validation
remains separate in the [release checklist](community-release-checklist.md).
