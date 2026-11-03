# Contributing to ac-deck

ac-deck is a Python/SDL2 launcher around original Assetto Corsa on Steam Deck.
The [v0.1.0-preview.1 release](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
provides an experimental installer/runtime and corresponding dependency
sources. Physical Deck behavior remains untested. Players use the
[installation guide](docs/installation.md) without an SDK or source checkout.

## Contributions and reports

Use [GitHub issues](https://github.com/alexandrefortes/ac-deck/issues) for bugs,
questions and proposals. Documentation corrections, reproducible installation
reports and focused navigation/control improvements are useful. Include exact
source/package version, SteamOS/Proton versions, expected behavior and sanitized
error/reproduction steps. Follow [troubleshooting](docs/troubleshooting.md).
Remove credentials, account details, private paths and unnecessary player data.
Distinguish synthetic/offscreen observations from actual Steam Deck use.

## Source and distribution

`ac-deck-dev` is canonical development; `ac-deck` is the curated community
distribution. Contributors need no private access. Shared launcher changes
are reviewed and reconciled with the canonical tree before export; public
docs, licenses, issues and releases retain distribution ownership. Preserve
community work and public ancestry.

Implementation belongs in `src/launcher/`. Keep `scripts/jogo_deck.py` and
`scripts/pratica_deck.py` stable; runtime modules do not import development
scripts or investigation models. The [export inventory](public-source-manifest.json)
records selected sources and actual hashes. The [change inventory](community-changes-manifest.json)
retains original deltas and their absorption, not another implementation.
A working-tree base identifies provenance; it does not claim uncommitted bytes
are contained in that base commit.

## Code checks

Use Python 3.13.5 and [pinned requirements](scripts/launcher-linux-requirements.txt)
in a reviewed persistent [SDK](docs/community-sdk.md) or explicit development
environment. From the public root:

```sh
python -B -m unittest discover -s tests -v
python -B scripts/jogo_deck.py --help
python -B scripts/pratica_deck.py --help
python -B scripts/build_launcher_linux.py --help
```

Run affected tests while editing and the full public selection before
integration. Fixtures are synthetic; private tests/assets are not prerequisites.
Builder unit tests simulate compilation. A real candidate separately needs the
[delivery cycle](docs/community-delivery.md), matching frozen sources,
SDK/native/font/notice inputs and compiled verification. The compiled receipt
separates two source-only child-interpreter fixtures from archived-code tests;
preserve that evidence boundary.

Keep changes focused and document behavior/ownership changes. Preserve exclusive
writes, atomic recovery, locks, filesystem checks, existing attachments,
Steam/Proton data and progression. Only the player opens Steam/the launcher and
starts races unless explicitly requested. Do not activate monitors or paid
services by inference; automated checks use synthetic/offscreen behavior.

## Licenses and third-party material

Project-owned code uses [PolyForm Noncommercial 1.0.0](LICENSE); its full text
defines permitted purposes, stated personal/organizational uses, notice duties
and fair-use provisions. Dependencies retain their own terms; purpose
restrictions do not supersede their modification/replacement or other rights.
Keep original notices and identify contribution provenance and permissions.

The interpreter excludes Berkeley DB/GDBM. Follow the exact
[dependency review](docs/dependency-license-review.md),
[sources/replacement instructions](docs/dependency-sources.md) and
[third-party notices](THIRD_PARTY_NOTICES.md#binary-distribution-review) for
binaries. Source access covers the matching release, not an unrelated older
archive. Preserve the PyInstaller exception, LGPL rights and selected
FTL/BSD/AFL routes within their stated scopes.

Game/DLCs, Steam/Proton, CSP archives, credentials, private history and unreviewed
mod/media are outside the public payload. CSP downloads separately from its
official source; optional cameras may require the author's account and exact
archive. Software licenses do not grant unrelated photo, voice or music rights.
The [content review](docs/content-rights.md) covers specified quotations and
jurisdictions; current gallery PNGs are omitted.

## Release evidence

Use the [preview/supported-release checklist](docs/community-release-checklist.md).
Each immutable candidate identifies sources, runtime, notices, companion,
checksums and promotion result. Tests, publication and physical acceptance
remain distinct. The updater has an [unchanged-product/Python contract](docs/update-and-recovery.md),
not a general migration mechanism. Do not replace older release bytes or claim
physical support from screenshots or automated checks.
