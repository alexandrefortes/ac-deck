# Troubleshooting

The current download is **v0.1.0-preview.2**, an experimental community
installer and runtime. Automated checks are recorded in
[build validation](build-validation.md); physical Deck support is unverified.

## Installation

| Message or symptom | Action |
| --- | --- |
| Terms were not accepted | Rerun the README command, read the disclaimer and explicitly select Yes if you agree. No is the default. |
| Enlarge the terminal | Enlarge Konsole so the whole acknowledgement is visible, then rerun the command. |
| Game not found | Install the original Assetto Corsa through Steam. Mount the game's SD card if applicable, then rerun the same command. A manual path must still identify a game declared in a Steam library. |
| Waiting for Steam | Use Steam → Exit and close the launcher/game. Setup continues when they are closed; after its timeout, rerun the same command. |
| Existing CSP file differs | Setup preserved a modified or incompatible required file. Keep the error and your current mod installation. Do not delete it or a receipt to force setup through. |
| Existing launch options | Supported literal environment assignments are preserved. Unknown wrappers are preserved and refused. Record your existing option privately and report the conflict. |
| Destination differs or is incomplete | The bootstrap preserves a different, edited or partial runtime. This is not the general updater. Keep the folder and use the version's recovery guidance. |
| Download or checksum failure | Preserve the error and retry the documented command. Report a persistent failure with the preview version; do not substitute another CSP/archive version or disable verification. |
| GLIBC/platform error | Run on Steam Deck/SteamOS x86_64 and use the normal SteamOS updater. This release requires GLIBC 2.38 or newer. |

No GitHub login, developer SDK or manual CSP copying is required. Do not run
the installer with sudo. See [installation](installation.md) for the full flow.

## Launcher and game

| Symptom | Useful evidence |
| --- | --- |
| First Steam Play fails | Record the error and actual selected Proton version. Missing default Proton folders are prepared by that same selected Proton, without a race; an existing or custom path is preserved. |
| Missing car, track or event | Confirm the relevant game/DLC/mod is installed. The launcher discovers the player's actual content. |
| Race does not start | Record selected content, graphics profile, SteamOS/Proton versions and the first error. Separate launcher startup from game startup. |
| Optional AI/dictation fails | Check the selected service and private credentials. Manual races do not require AI. Remove credentials from reports. |
| Settings/progress seem missing | Stop changing that data and identify the installation/attachment in use. Follow [recovery](update-and-recovery.md); do not reset progress or reinstall the game as a generic fix. |

The user starts Steam, the launcher and each race. Installing the preview does
not prove controls, offline use, performance or game compatibility.

## Report a problem

Use [GitHub issues](https://github.com/alexandrefortes/ac-deck/issues). Include
the preview version, SteamOS and actually selected Proton versions, steps,
expected/observed result and a sanitized terminal error. Keep account IDs,
credentials, complete Steam VDF files, prefixes and private session data local.
