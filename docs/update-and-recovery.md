# Updates and recovery

There is no validated public package or update procedure yet. A reviewed release must document its supported update path and which earlier versions it can update safely.

## Data to preserve

An update must keep the existing game attachment and the player's data. This includes launcher preferences, favorites, generated proposals, Rogue progression, recorded attempts, optional API credentials and the game's own saves and configuration.

The exact storage locations depend on the supported installation and Steam/Proton configuration. A release must identify the effective paths before asking a user to copy, move or replace them. Full package portability is not established by moving the launcher folder alone.

Keep backups local. Credentials, Steam account data and private session records do not belong in a public issue or repository.

## Before updating

1. Read the target release's compatibility notes, data locations and recovery instructions.
2. Close the launcher and any running race normally.
3. Back up the documented player-owned data and retain the previous verified package in a separate folder.
4. Confirm that the target package matches its published checksum and intended source revision.

## Requirements for the supported update path

- Preserve the existing Steam entry, game attachment and player-selected settings.
- Replace only files owned by the launcher distribution.
- Preserve unknown files, caches and player-modified content according to the documented ownership rules.
- Keep source provenance, runtime metadata and the installed payload consistent.
- Describe any data migration and its compatibility with rollback before applying it.

Exact update commands will accompany the reviewed updater. Reinstalling the game or deleting a Proton prefix is not a normal launcher update step.

## Recovering from a failed update

Keep the failed package and its diagnostic information available for inspection. Use the recovery method documented for that release to restore the previous verified runtime while preserving current player data.

If a release changes a data format, restoring older binaries may also require that release's documented data recovery procedure. A runtime rollback must not silently replace newer progress with an older backup.

If the release does not provide a verified recovery procedure, report the failure with the old and new versions, the failed step and sanitized error output. See [troubleshooting](troubleshooting.md).

## Release acceptance

Public update support requires checks against existing game attachments, settings, progress, caches and interrupted updates, followed by recorded Steam Deck use. The [community release checklist](community-release-checklist.md) tracks these requirements.
