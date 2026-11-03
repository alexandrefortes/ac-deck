# Community preview and supported-release checks

Preview 1 was withdrawn after confirmed dependency advisories. Its preserved
[review](../archive/dependency-license-review-v0.1.0-preview.1.md) describes those
older bytes; follow the [current security decision](security-review.md).

**v0.1.0-preview.2 is experimental.** Automated checks support its recorded
candidate; physical Steam Deck installation, controls, races and performance
have not been validated. Those physical checks are conditions of a supported
release, not a claim made by this preview.

The [release page](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.2)
provides runtime, bootstrap, checksums and dependency sources. The source tag,
[export inventory](../public-source-manifest.json),
[dependency inventory](../licenses/dependency-sources.json) and promotion receipt
bind the exact distribution. Follow the [delivery workflow](community-delivery.md);
do not rebuild or replace published bytes.

## Preview preparation

- [x] Preserve public ancestry/contributions; select canonical launcher sources and record actual hashes and provenance.
- [x] Retain PolyForm Noncommercial 1.0.0 for project-owned code and independent dependency licenses/rights.
- [x] Review a separate CPython 3.13.5 SDK without Berkeley DB/GDBM; preserve earlier SDK and binary records.
- [ ] Match the final 69 component records, 278 exact source/notice/recipe files and 103 original notices. Select FTL for FreeType, BSD-3-Clause for Zstandard and AFL-2.1 for D-Bus with full notices and applicable source access.
- [x] Retain LGPL replacement/reverse-engineering rights, sources and build/replacement instructions, and the PyInstaller bootloader exception within its stated scope.
- [x] Record the quotations' specific [US/Brazil assessment](content-rights.md); omit current unverified PNG gallery and private album/Toasty media while preserving historical evidence.
- [x] Exclude game/DLCs, Steam/Proton, CSP archives, credentials and player data from the community payload.
- [x] Provide autonomous setup, bounded Steam-close wait, discovery/account selection, literal launch-option preservation and restoration receipts. Keep game/race starts under player control.
- [x] Keep CSP 0.3.1 as the only required game mod, downloaded separately from its official source with the pinned hash. Its publisher calls it untested; a digest does not prove compatibility.
- [x] Confirm final receipts for 207 public source tests and 130 compiled tests without errors/failures/skips, ten offscreen compositions, CLI, bootstrap and relocation. Two child-interpreter fixtures are explicitly source coverage, not compiled Python-subprocess coverage.
- [x] Document installation, contributions, issue reporting and recovery without private access or an end-user SDK.

## Promotion of the exact preview

- [ ] Run `git diff --check` against the selected public changes and resolve whitespace errors.
- [ ] Recheck the exact six Python pins against current reviewed GitHub advisory ranges; record date, aliases, pagination and matching count. Block publication on unresolved relevant advisories.
- [ ] Confirm Pillow 13.0.0 and setuptools 84.1.0 in the frozen inputs and reviewed SDK, then verify the candidate's actual Pillow payload and notices. Preserve preview 1 unchanged.
- [ ] Confirm final runtime/source hashes, ELF mapping, corresponding sources, notices, source/compiled checks and shared-library replacement evidence for this candidate.
- [ ] Verify anonymous recipient access to the published checksums/bootstrap/runtime/source companion and the documented install command.


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
