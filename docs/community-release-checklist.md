# Community preview and supported-release checks

**v0.1.0-preview.1 is experimental.** Automated checks support its recorded
candidate; physical Steam Deck installation, controls, races and performance
have not been validated. Those physical checks are conditions of a supported
release, not a claim made by this preview.

The [release page](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
provides runtime, bootstrap, checksums and dependency sources. The source tag,
[export inventory](../public-source-manifest.json),
[dependency inventory](../licenses/dependency-sources.json) and promotion receipt
bind the exact distribution. Follow the [delivery workflow](community-delivery.md);
do not rebuild or replace published bytes.

## Preview preparation

- [x] Preserve public ancestry/contributions; select canonical launcher sources and record actual hashes and provenance.
- [x] Retain PolyForm Noncommercial 1.0.0 for project-owned code and independent dependency licenses/rights.
- [x] Review a separate CPython 3.13.5 SDK without Berkeley DB/GDBM; preserve earlier SDK and binary records.
- [x] Prepare 67 component records, 252 exact source/notice/recipe files and 84 original notices. Select FTL for FreeType, BSD-3-Clause for Zstandard and AFL-2.1 for D-Bus with full notices and applicable source access.
- [x] Retain LGPL replacement/reverse-engineering rights, sources and build/replacement instructions, and the PyInstaller bootloader exception within its stated scope.
- [x] Record the quotations' specific [US/Brazil assessment](content-rights.md); omit current unverified PNG gallery and private album/Toasty media while preserving historical evidence.
- [x] Exclude game/DLCs, Steam/Proton, CSP archives, credentials and player data from the community payload.
- [x] Provide autonomous setup, bounded Steam-close wait, discovery/account selection, literal launch-option preservation and restoration receipts. Keep game/race starts under player control.
- [x] Keep CSP 0.3.1 as the only required game mod, downloaded separately from its official source with the pinned hash. Its publisher calls it untested; a digest does not prove compatibility.
- [x] Exercise 207 public source tests and 130 compiled tests without errors/failures/skips, ten offscreen compositions, CLI, bootstrap and relocation. Two child-interpreter fixtures are explicitly source coverage, not compiled Python-subprocess coverage.
- [x] Document installation, contributions, issue reporting and recovery without private access or an end-user SDK.

## Promotion of the exact preview

Before publishing, compare runtime and source companion with the
[reviewed identities](dependency-license-review.md#exact-distribution).
Confirm final ELF mapping, notices, source tag, payload exclusions and candidate
receipts. Upload immutable runtime, bootstrap, source companion and checksums
to the same release, verify recipient access and record promotion. Publish only
reviewed sources/assets. A checklist does not create a tag, upload an asset or
prove availability.

The private suite recorded 3,158 tests with 45 skips. Its fixtures and count are
not prerequisites for public contributors. Final public source/package receipts
are the relevant reproducible checks.

## Before calling a release supported

- [ ] Verify physical Deck installation, account selection, Steam persistence and launch-option restoration after closing/reopening Steam.
- [ ] Verify default graphics/controls, first Proton initialization, actual races, saves, progression, suspend/restart behavior and claimed hardware features.
- [ ] Exercise packaging update/recovery on the real attachment while preserving settings, saves, caches and Proton data.
- [ ] Review first-use instructions with a new player; record SteamOS/Proton versions, failures and acceptance.
- [ ] Measure performance/offline/portability claims for their stated version and scenario.

Record these in the [Deck plan](deck-validation-plan.md). Until then, retain the
experimental preview label and its limits.
