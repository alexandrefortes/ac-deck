# Physical Steam Deck validation plan

**Status: prepared, not executed.** This plan is for the experimental
**v0.1.0-preview.1** package. Automated validation, public availability,
physical observations and user acceptance remain separate. Preparing or
publishing the preview does not start a monitor, Steam, the launcher or a race.

## Record the exact candidate

- Archive: `ac-deck-linux-x86_64.tar.gz`, 45773729 bytes.
- Archive SHA-256: `f6e0b14ca8480217793d619bc7d6edb31a2666f486262681cecf301b79fbefb1`.
- Executable SHA-256: `357309498277ddf88c2163231d5c0bfe426fb7628c895ffeca1e010e5f4201db`.
- Manifest SHA-256: `5df8d203d75c865aeb546c5288288a00e52e9c0384f4b0a41ddb34d4ba6ab126`.
- Required GLIBC reaches 2.38. Record actual Deck model, SteamOS,
  Steam and selected Proton versions; build-host versions do not prove Deck compatibility.

Use the [release record](https://github.com/alexandrefortes/ac-deck/releases/tag/v0.1.0-preview.1)
for the matching source tag, installer, checksums and dependency sources.

## New user's installation

Use the public [installation tutorial](installation.md) exactly as written.
The user needs a legitimate game installed through Steam, internet and space;
they open Konsole and paste the single README command, then explicitly accept
the disclaimer if they agree. No GitHub login or developer assistance should
be needed. The user closes Steam/game when setup asks and opens Steam afterward.

Record whether game discovery works on internal storage and an SD library,
whether a unique game/account is selected automatically, and whether ambiguous
cases are explained without requiring knowledge of filesystem internals.
Record CSP download/hash verification, reuse of identical files, missing-file
repair, preservation/refusal of modified files and recognized managed migration.
Verify repeating the command after a setup interruption preserves player data.

If the Deck already has development CSP or launch wrappers, record that as an
existing-mod installation, rather than calling it clean. Preserve the current
game, Steam options, Proton setup and local backups. Do not erase a prefix,
Cloud data, mods or saves to manufacture a new-user scenario.

## First Steam Play and races

The user selects the original Assetto Corsa Steam entry and presses Play.
Verify launch-option persistence after closing/reopening Steam. On first use,
missing default Proton Documents should be initialized through the selected
Proton without starting a race; existing Documents/custom paths must remain.

Check launcher startup, discovered content, 1280 × 800 readability, controller
navigation and normal exit. The user then explicitly starts a short manual
race with installed content. Check CSP Performance first, preserving the saved
profile for restoration. Verify correct content/settings, finish/cancellation,
return to launcher, settings/history/progress and no duplicate results.

Check optional/offline/suspend scenarios separately. Record content/grid,
resolution/profile, refresh/power settings, duration, actual frametimes/FPS and
failures for any performance claim. Configured values or screenshots are not
measurements. Missing hardware or skipped cases remain unverified.

## Recovery and updates

With Steam/game closed, test the documented `restore-steam` command and compare
the recorded original option. It restores only the still-owned Steam option,
not CSP, game files, runtime or newer progress. Unknown independently edited
options must be preserved. Do not restore an older save over new progress.

This preview is for new installation. The [packaging updater](update-and-recovery.md)
is limited to unchanged product/Python identities; the older packaging-only
transition does not authorize upgrading into this functional preview. A future
functional update requires a reviewed migration/recovery contract.

## Record the result

For every scenario, record candidate/environment identity, initial state,
steps, expected/observed result, sanitized evidence and one of `passed`,
`failed`, `blocked` or `not tested`. Record user acceptance separately.
Keep account details, credentials, VDFs and raw private data out of public reports.
A supported release requires actual physical evidence for the claims it makes;
the experimental preview does not imply those gates passed.
