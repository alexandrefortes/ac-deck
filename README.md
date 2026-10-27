# ac-deck

A controller-friendly launcher for the original Assetto Corsa on Steam Deck.

**Community preview:** this branch presents the application and its interface.
Source code and a compiled community candidate are prepared locally; their
public release awaits the first-party license decision. There is no public
installer or downloadable runtime release yet.

[![Drive screen with authored demonstration content](docs/screenshots/ac-deck-drive-1280x800.png)](docs/screenshots/ac-deck-drive-1920x1200.png)

Captured from the real SDL interface renderer using fictional demonstration
cars, circuits and original schematic artwork. These are interface previews,
not race captures or performance measurements. Click an image for 1920 × 1200.

## Features

| Area | Existing launcher functionality |
| --- | --- |
| Drive | Browse installed cars and tracks and configure a manual session. |
| Events | Browse events from installed campaigns. |
| Event Synthetizer | Review generated race proposals, with optional AI generation. |
| Rogue | Persistent challenges, progression and rewards. |
| History | Inspect recorded attempts and restore race setups. |
| Settings | Configure graphics, controls, assists and optional AI features. |

The launcher uses the original simulator through Steam/Proton. Cars, tracks and other installed content come from the player's installation.

## Gallery

| Events | Event Synthetizer |
| --- | --- |
| [![Events screen with demonstration campaign data](docs/screenshots/ac-deck-events-1280x800.png)](docs/screenshots/ac-deck-events-1920x1200.png) | [![Event Synthetizer screen with a demonstration race proposal](docs/screenshots/ac-deck-synth-1280x800.png)](docs/screenshots/ac-deck-synth-1920x1200.png) |

| Rogue | Settings |
| --- | --- |
| [![Rogue screen with demonstration challenge and progression data](docs/screenshots/ac-deck-rogue-1280x800.png)](docs/screenshots/ac-deck-rogue-1920x1200.png) | [![Settings screen showing launcher configuration options](docs/screenshots/ac-deck-settings-1280x800.png)](docs/screenshots/ac-deck-settings-1920x1200.png) |

[Capture provenance and image manifest](docs/screenshots/README.md).

Community builds use native graphics profiles by default. CSP-related controls
shown in the previews require a separately supplied CSP kit; CSP is not bundled.

## Requirements

- Steam Deck running SteamOS/Linux.
- Steam and a legitimate copy of the original Assetto Corsa, plus any DLC required by the selected content.
- The game installed and working with the player's Steam/Proton setup.
- Optional AI generation and dictation require their configured services, network access and API credentials.

## Availability and contribution

The current launcher has passed automated checks, and a community candidate
has been built without bundled CSP, mods or private media. Source licensing,
public package publication and physical Steam Deck validation remain separate
steps in the [release checklist](docs/community-release-checklist.md).

A legitimate Steam installation of Assetto Corsa remains required. Game/DLC
files, Steam credentials and player data are not part of this project.

Documentation corrections, preview feedback and reproducible reports are
welcome through [GitHub issues](https://github.com/alexandrefortes/ac-deck/issues).
Read [CONTRIBUTING](CONTRIBUTING.md). Remove account information, API keys and
private paths from reports. Source build and installation instructions will
accompany the licensed source/package release.
