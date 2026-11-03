# Install ac-deck on Steam Deck

This guide installs **v0.1.0-preview.1**, an experimental Linux x86_64 preview.
It has passed its automated checks; physical Steam Deck behavior has not been
validated. The earlier `community-preview-001` archive is a different version
and does not contain this installer.

## Before you start

- Install the original **Assetto Corsa** (Steam App ID 244210) on the Deck's
  internal storage or a Steam library on a mounted SD card. The launcher uses
  your legitimate game, DLCs and Steam account.
- Keep your working Proton selection. ac-deck does not replace Proton, create
  another Steam account or remove your prefix/saves.
- Use SteamOS with GLIBC **2.38 or newer**, internet access for setup,
  and at least **1 GB free for the launcher, CSP and staging**, in addition to
  the game's storage. Existing mods and backups may need more space.
- Finish any race and close the game. Setup needs Steam fully closed while
  changing its launch option; follow the installer's message.

## One command

1. Switch to **Desktop Mode**.
2. Open **Konsole** from the application launcher.
3. Paste the whole command below and press Enter:

```sh
bash -o pipefail -c 'curl --fail --show-error --location --proto "=https" --proto-redir "=https" https://raw.githubusercontent.com/alexandrefortes/ac-deck/v0.1.0-preview.1/install.sh | bash'
```

No GitHub login is needed. Do not add `sudo`. No developer SDK, Python packages,
Git or compilation is required; the launcher includes its runtime. The small
download verifier uses the system's Python 3.10 or newer. A missing required
system command or incompatible GLIBC stops with an explanation.

The installer:

Before downloading or installing the runtime, it displays the disclaimer and
license acknowledgement. **No** is selected by default. Use the arrow keys
and Enter, click a choice in Konsole, or press Y/N. Only an explicit **Yes**
continues. Enter on No, N, Escape, Ctrl+C or a closed terminal stops setup
without creating the installation. The disclaimer is also in the [README](../README.md#disclaimer).

1. Downloads the matching bootstrap and runtime and checks their fixed SHA-256
   values before starting setup.
2. Installs the launcher under `~/.local/share/ac-deck` (or the user's configured
   XDG data directory), without overwriting a different existing distribution.
3. Discovers Assetto Corsa through Steam's declared libraries, including a
   mounted SD card. With one valid game, no path entry is needed. If none is
   found, it explains how to install the game through Steam and offers a manual
   path only for an existing installation already registered in Steam.
4. Downloads the pinned **CSP 0.3.1** from its official HTTPS source, checks the
   archive and prepares the selected files. CSP is not mirrored in our release.
5. Reuses files matching the required CSP version, installs missing required
   files and preserves unrelated files. A conflicting version or modified
   required file is preserved and reported; setup does not silently replace
   another mod installation. A recognized previously managed CSP version uses
   the existing verified migration with backup and recovery.
6. Selects the Steam account automatically when it is unambiguous, preserves
   supported literal launch-option settings and saves a local restoration
   receipt before configuring the original Assetto Corsa entry.
7. Prints the installation result and next action. It does not open Steam,
   start the launcher or start a race.

If multiple games/accounts are plausible, select from the list shown in the
terminal. If Steam is still running, close it completely with **Steam → Exit**
and follow the message. Unknown wrappers or conflicting files require a
decision; the installer leaves them intact. Do not delete CSP files, launch
options, locks or Proton data to force setup through an error.

If setup stopped after downloading the launcher, rerun the same command. It
reuses that installation only when every distribution file still matches the
verified archive; it leaves player files untouched. A different or edited
distribution is refused, rather than being treated as an update.

## Start playing

When setup succeeds, open Steam yourself, select the original **Assetto Corsa**
entry and press **Play**. If the default Proton user folders do not exist yet,
the launcher asks that same Steam-selected Proton to prepare them without
starting a race. Existing folders and custom paths are preserved. The launcher
then opens. Select installed content in Drive and start a race when ready. You can return to Game Mode and
use the same Steam entry.

The default controller script is Gamepad Force supplied by CSP; the default
camera is Original. AGA, GT5/BACC cameras, Sidekick, Sol, Pure and Content
Manager are not installation prerequisites. Additional cameras may require
the author's separately acquired exact archive. No account-gated mod download
or private media pack is part of this command. See
[third-party integrations](third-party-integrations.md).

CSP's publisher labels the pinned 0.3.1 build untested. Matching its hash
confirms selected bytes and does not establish game/Proton compatibility.
Manual races do not require AI accounts or paid services.

## Recovery and reporting

The launcher keeps its setup/Steam receipts and private attachment under its
installation's `local/` directory. Keep them; do not post credentials, account
IDs or complete Steam VDF files in an issue.

To restore only the recorded original Steam launch option, close Steam and
the game, open Konsole and run:

```sh
"${XDG_DATA_HOME:-$HOME/.local/share}/ac-deck/ac-deck" restore-steam
```

This restores the selected account's option only if it still matches the
recorded installed value. It does not remove CSP, delete player data or roll
back the runtime. Stop and preserve changed files if restoration reports a
conflict. See [updates and recovery](update-and-recovery.md) for the available
packaging recovery procedure and its limits; functional upgrades need their
own migration contract.

For failures, include the preview version, SteamOS/Proton versions, step and
sanitized terminal error in a [GitHub issue](https://github.com/alexandrefortes/ac-deck/issues).
Read [troubleshooting](troubleshooting.md). Installation, actual play,
performance and acceptance are recorded separately.

## Exact release and source

The [release page](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
provides the runtime, installer, SHA256SUMS, corresponding dependency sources
and promotion record. The source tag identifies the exact public code; the
record binds its hashes to the frozen candidate. Runtime archive SHA-256:

```text
f6e0b14ca8480217793d619bc7d6edb31a2666f486262681cecf301b79fbefb1
```

## Building from source

For source builds, use [community delivery](community-delivery.md), the
[persistent SDK guide](community-sdk.md) and [dependency sources](dependency-sources.md).
Contributors can use this public repository without private access. The
one-command installation above uses a compiled package and does not require
those development steps.
