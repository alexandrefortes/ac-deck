# ac-deck

A controller-friendly launcher for the original Assetto Corsa on Steam Deck.

**Experimental preview v0.1.0-preview.1:** automated source/package/installation
checks passed. Physical Steam Deck installation, controls, real races and
performance have not been validated. Report your SteamOS/Proton versions and
the observed result; do not treat the preview as a supported release.

## Install on Steam Deck

Install the original **Assetto Corsa** through Steam first and keep your working
Proton configuration. Then switch to **Desktop Mode**, open **Konsole**, and
paste this command:

```sh
bash -o pipefail -c 'curl --fail --show-error --location --proto "=https" --proto-redir "=https" https://raw.githubusercontent.com/alexandrefortes/ac-deck/v0.1.0-preview.1/install.sh | bash'
```

No GitHub login, Git checkout, SDK, compilation or manual file copying is needed.
The installer downloads the verified launcher, discovers the game's Steam
library on internal storage or an SD card, downloads CSP from its official
source, and configures the original Assetto Corsa Steam entry. It reuses
verified compatible files and preserves unrelated mods and player data.
An ambiguous game/account selection or conflicting modified file needs your
decision; the installer explains the problem instead of overwriting it.
Before installation, read the disclaimer in the terminal and explicitly
select **Yes** to continue. **No** is selected by default; arrows, mouse,
Y/N and Enter work in Konsole. Refusing stops installation.

After setup, open Steam and select **Assetto Corsa → Play**. The user starts
the launcher and every race. Read the [installation guide](docs/installation.md)
for requirements, setup behavior and recovery.

## What it does

- Browse installed cars and tracks and configure races in Drive.
- Use installed Events, generate races with Event Synthetizer, and play Rogue.
- Keep History, preferences, favorites and progression.
- Configure graphics, assists, controller settings and optional integrations.

The launcher uses the game and DLCs you own. It does not supply the game,
Steam, Proton, credentials or private mod/media packs. **CSP 0.3.1 is the only
required game mod** and is downloaded separately during setup. Gamepad Force
comes with CSP. AGA and additional cameras are optional; see
[third-party integrations](docs/third-party-integrations.md).
Optional AI and dictation need their own configured services and credentials.
Manual races do not require AI.

## Disclaimer

ac-deck is a community project, unaffiliated with the game, Steam or CSP
publishers. As far as applicable law allows, it is provided **as is, without
warranties**, and its creator is not liable for problems or damages arising
from its use. This notice does not remove rights that applicable law protects.

You may modify the project-owned code for personal, noncommercial use under
[PolyForm Noncommercial 1.0.0](LICENSE). The license also permits other stated
purposes and preserves applicable fair-use rights. Third-party components
retain their own licenses; this disclaimer does not replace those terms.

## Downloads and help

- [Preview, checksums and corresponding dependency sources](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
- [Installation](docs/installation.md), [updates and recovery](docs/update-and-recovery.md)
- [Troubleshooting](docs/troubleshooting.md), [report a problem](https://github.com/alexandrefortes/ac-deck/issues)
- [Contributing and source checks](CONTRIBUTING.md), [release checks](docs/community-release-checklist.md)

Project-owned code uses [PolyForm Noncommercial 1.0.0](LICENSE). Dependencies
keep their own terms and rights; see [third-party notices](THIRD_PARTY_NOTICES.md)
and [content rights](docs/content-rights.md). Development is maintained in
`ac-deck-dev`; this repository is the curated community distribution.
