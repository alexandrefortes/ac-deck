# Installation and availability

Source is available in this repository under [PolyForm Noncommercial 1.0.0](../LICENSE), with the community builder and synthetic tests. An experimental runtime preview and corresponding dependency sources are available; physical Steam Deck validation has not yet been performed. You can inspect and test the source using the commands below.

## What the project provides

The [source inventory](../public-source-manifest.json) records the reviewed launcher export. The community builder creates the project's runtime and records its inputs. The launcher uses the player's installed original Assetto Corsa through Steam/Proton.

Game/DLC files, Steam account data, CSP archives and third-party mod/media payloads are outside this public distribution. Any optional integration must identify its supported version, legitimate acquisition route and setup requirements before being presented as supported.

## Prerequisites

- A Steam Deck running SteamOS/Linux. Windows and other devices are not established public support targets.
- Steam and a legitimate copy of the original Assetto Corsa, with the DLC required by the selected cars, tracks or events.
- A working game installation using the player's normal Steam/Proton setup.
- Enough free storage for the reviewed package and any backup required during installation or updates. Package size and supported versions will be listed with a release.

The local candidate targets Linux x86_64 with GLIBC 2.39 as its highest required symbol version. Its Python runtime is bundled; Python 3.13.5 is required when compiling from source. This candidate result does not establish compatibility with an untested SteamOS/Proton combination.

AI generation and dictation are optional. They require their configured services, network access and API credentials; provider accounts and charges are separate from the launcher. Manual race configuration does not require AI.

No public compatibility matrix is validated yet. A future release must identify the SteamOS, Proton and launcher versions that were actually tested.

## Installing a reviewed release

An [experimental Linux x86_64 preview](https://github.com/alexandrefortes/ac-deck/tree/community-preview-001) is available with its [checksums](https://github.com/alexandrefortes/ac-deck/blob/community-preview-001/SHA256SUMS) and corresponding dependency sources. It requires GLIBC 2.39; SteamOS and physical Steam Deck compatibility have not been verified. This is a preview, not a supported installer or update procedure.

Download `ac-deck-linux-x86_64.tar.gz` and verify its SHA-256 against `SHA256SUMS` before extracting. The archive contains the `ac-deck-linux-x86_64/` folder, executable, notices and an informational `LEIA-ME.txt`. The companion `ac-deck-dependency-sources.tar.gz` contains corresponding LGPL library sources.

The preview runtime SHA-256 is `c5180c63af36ab329418f952d0e4c7fbeafceb122fbb5be185eeed5372ff1f7c`. Its dependency-sources archive SHA-256 is `ceb3dc08c1a10b39485caf7fe6dcf29aa214794a0f3327dc17f4d98fb02527d3`.

The supported installation flow must cover:

1. Selecting the reviewed package for the documented platform and checking its published checksum.
2. Extracting into a dedicated writable launcher folder.
3. Selecting the existing game installation and documenting which settings and data the launcher owns.
4. Configuring the documented Steam entry and preserving the player's existing Proton setup.
5. Starting the launcher and checking the discovered content before the player starts a race.

A supported installation procedure requires the checks tracked in the [release review](community-release-checklist.md).

## Building from source

The real entrypoint is [`scripts/build_launcher_linux.py`](../scripts/build_launcher_linux.py). Use its `--community` profile on **Linux x86_64**, with **CPython 3.13.5** and the [hash-pinned Python dependencies](../scripts/launcher-linux-requirements.txt). Project-owned code is subject to [PolyForm Noncommercial 1.0.0](../LICENSE), including its expressly permitted personal and organizational uses. Third-party libraries retain their own terms; a local build does not by itself establish that a combined binary distribution meets those terms.

From the repository root, create an explicit local environment using your Python 3.13.5 interpreter:

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r scripts/launcher-linux-requirements.txt
python -B -m unittest discover -s tests -v
```

The pinned wheels target CPython 3.13 on Linux x86_64. They are not a cross-platform dependency recipe.

Compilation also requires `readelf`, selected regular native-library files including `libSDL2-2.0.so.0`, a selected TTF font and the matching runtime/library/font license notices. Obtain those inputs legitimately for your SDK; the builder neither downloads them nor follows library-input symlinks. It requires actual regular files. The font and its notice must be covered by your selected notices.

Replace the three `/path/to/...` examples below with your reviewed local SDK inputs. Choose a new batch name for each build; existing batches are preserved.

```sh
python -B scripts/build_launcher_linux.py \
  --community \
  --lote community-local-01 \
  --bibliotecas /path/to/regular-native-libraries \
  --font /path/to/DejaVuSans.ttf \
  --licenses-dir /path/to/runtime-library-font-notices
```

The builder writes the following under `local/work/community-local-01/`:

- `ac-deck-linux-x86_64/`: candidate directory with the `ac-deck` executable, runtime, notices, `build-info.json` and `manifest.json`.
- `ac-deck-linux-x86_64.tar.gz`: candidate archive.
- `result.json`: output paths, archive hash and build metadata.

The community profile rejects the private-payload options for CSP, camera mods, media and reused deliveries before reading those inputs. It does not bundle the game, DLCs, Steam data, a Proton prefix, CSP or mod/media archives. See [third-party notices](../THIRD_PARTY_NOTICES.md).

You can check the candidate's informational CLI without opening the launcher window or a race:

```sh
local/work/community-local-01/ac-deck-linux-x86_64/ac-deck --help
```

A successful compilation produces a local candidate, not a published release or proof of Steam Deck compatibility. When distributing your own build, include the first-party license and notice, relevant third-party notices and corresponding dependency sources; review the [LGPL requirements](../THIRD_PARTY_NOTICES.md#binary-distribution-review). The builder does not automatically add the first-party LICENSE and NOTICE. Physical Steam Deck validation remains separate. Record source hashes, native inputs, notices, CLI/resource checks and actual platform observations as part of [release review](community-release-checklist.md).

## What counts as verified

Interface screenshots use demonstration data. Automated checks and packaged CLI checks must be recorded separately from observed Steam Deck startup, controller behavior, real races, offline use and performance.

See [updates and recovery](update-and-recovery.md), [troubleshooting](troubleshooting.md) and the [community release checklist](community-release-checklist.md).
