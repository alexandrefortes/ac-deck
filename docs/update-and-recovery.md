# Update packaging and recover an installation

**v0.1.0-preview.3 is a new-install preview.** The one-command bootstrap may repeat
setup for this exact verified runtime; it does not upgrade an older or edited
distribution. Preview 3 changes product sources after preview 2. Continue using
your existing installation and its progress until a functional migration is
available. The packaging-only transition tested below uses older archives.

The current updater supports corrections to packaging, notices and bundled
dependencies while the product source, Python version and data layout remain
unchanged. It does **not** perform a general launcher upgrade or migrate player
data. A different product source identity or Python version is refused for both
update and rollback until a reviewed migration contract exists.

This procedure is prepared and tested with synthetic installations. It does not
mean that an update has been applied to your Steam Deck or accepted in a race.
Publication and the [dependency license review](dependency-license-review.md)
remain separate gates.

Preview 1 was withdrawn for dependency security corrections. Do not install
or roll back to it. Keep an affected installation intact for diagnosis and
use the documented restoration procedure; the README command refuses a
different existing distribution rather than silently replacing it.

## Requirements

Use Python 3.10 or newer on Linux x86_64, including WSL with the installed destination on a Linux
filesystem that preserves file modes. The source checkout may remain on a
Windows drive. Do not install or update the runtime on a Windows drive that
reports every file as executable.

Close Steam, ac-deck and the game yourself before starting. Keep them closed
until the command reports completion. `--closed` acknowledges this requirement;
the tool also checks the current user's Linux process list. It neither starts
nor stops those applications and never changes Steam options or a Proton prefix.
The process check and filesystem comparisons cannot lock out an unrelated writer
that ignores the update lock. An observed conflicting edit stops the operation
and preserves the files for review.

Use the versioned source checkout of this public repository, outside the installed
runtime directory. The updater uses Python's standard library and these public
files; it is not a standalone one-file download:

- `scripts/update_ac_deck.py` and `scripts/install_ac_deck.py`;
- `scripts/ciclo_entrega_lib/__init__.py` and `common.py`;
- `src/launcher/__init__.py`, `file_io.py` and `steam_install_options.py`.

Keep the public checkout together instead of constructing an incomplete helper
directory. The runtime archive and any corresponding-source companion archive
are separate downloads; a source companion is not installed over the runtime.

## First update of an existing community installation

Obtain the reviewed new runtime archive and its expected SHA-256 from the release
publisher. Also retain the archive and expected SHA-256 used for the currently
installed runtime. Do not substitute a checksum calculated from an untrusted
download for a publisher-provided expected checksum.

The first update needs both archives because the existing community manifest
records file hashes and sizes without recording original executable modes or an
updater ownership receipt. The old verified archive proves that ownership before
the tool changes any installed distribution file. An older preview without the
current community metadata, installer modules or source identity is refused.

From the public source checkout, replace the placeholders with absolute paths:

```sh
python3 -B scripts/update_ac_deck.py update \
  --destination /home/deck/.local/share/ac-deck \
  --archive /home/deck/Downloads/new/ac-deck-linux-x86_64.tar.gz \
  --sha256 NEW_EXPECTED_SHA256 \
  --current-archive /home/deck/Downloads/current/ac-deck-linux-x86_64.tar.gz \
  --current-sha256 CURRENT_EXPECTED_SHA256 \
  --closed
```

The fixed installation path stays the same. Its game attachment, CSP kit,
progress, preferences, private credentials and existing Steam entry stay in
place. `local/`, `csp/`, game files, Steam data and Proton paths cannot be claimed
as managed runtime files by an archive manifest.

The allowed distribution selection is the old/new manifest union under
`_internal/`, `licenses/` and the existing top-level executable, metadata and
notice files. The tool verifies the complete staged archive, hashes, sizes,
executable modes and community metadata before replacing files. It refuses a
locally edited managed file, an unknown collision, traversal, a selected link,
case aliases, changed frozen inputs or an incompatible product/Python identity.
Unknown files outside that managed selection are preserved rather than scanned
as player data or added to the distribution manifest.

Success prints JSON with `status: "complete"`, the transaction ID, direction,
destination and manifest hash. It does not run setup or open the launcher.

## Subsequent packaging corrections

After successful first adoption, ownership is anchored by a local receipt.
Omit the old archive options; the updater backs up the current managed files
after verifying them against that receipt:

```sh
python3 -B scripts/update_ac_deck.py update \
  --destination /home/deck/.local/share/ac-deck \
  --archive /home/deck/Downloads/new/ac-deck-linux-x86_64.tar.gz \
  --sha256 NEW_EXPECTED_SHA256 \
  --closed
```

Changing only the builder or notice bytes does not change the product identity.
The conservative compatibility check compares every `src/launcher/` source hash,
the stable game/practice entrypoints, Python version and architecture. It does
not compare all ELF hashes or prove that arbitrary native-library replacements
are compatible; the exact dependency changes need their own candidate checks.
A change to the launcher Python sources remains outside this procedure even if a maintainer believes
its data format would remain compatible. There is no override flag that merely
asserts compatibility.

## Resume an interrupted operation

Keep the installed path, journal and transaction directories intact. Run:

```sh
python3 -B scripts/update_ac_deck.py resume \
  --destination /home/deck/.local/share/ac-deck \
  --closed
```

The tool retains its verified new distribution and old runtime backup under
`local/distribution-update/transactions/ID/`. It can resume without the original
external download paths. Before continuing, every managed path must match the
recorded old or new hash, size and mode. Already replaced or deleted files are
recognized; the manifest and installed ownership receipt are confirmed last.
A lost final response is reconciled from those observed effects. A missing final
owned receipt can be reconstructed only when the frozen plan, journal and exact
completed distribution still agree. An existing edited receipt is preserved
and refused.

Partial temporary copies are preserved with unique `.ac-deck-update-*.new`
names. Resume uses a fresh temporary copy; it never adopts unknown partial bytes.
Do not delete locks, journals, backups or failed attempts by age or PID. The OS
lock is released when the process exits; the lock file's existence does not mean
that the updater is still running. Review a conflicting path before deciding
how to retain it and recover. The tool does not provide an unrestricted overwrite
or force option.

## Roll back the last completed packaging correction

Close Steam, the launcher and the game again, then run:

```sh
python3 -B scripts/update_ac_deck.py rollback \
  --destination /home/deck/.local/share/ac-deck \
  --closed
```

Rollback restores only the previous managed distribution files and manifest
from the verified backup. Player progress saved after the update stays newer;
`local/`, the game attachment, CSP and Steam/Proton data are not restored from an
older snapshot. This is safe only within the unchanged product/Python/data-layout
identity described above. An incompatible runtime or edited backup is refused.

Finish an interrupted update with `resume` before requesting rollback. If a
rollback itself is interrupted, `resume` continues that recorded rollback.
Repeated recovery of an already complete operation verifies it without repairing
later local runtime edits. A new packaging correction after rollback starts a
new transaction and retains the earlier transaction's backups.

`restore-steam` is a separate operation for undoing an explicitly installed Steam
launch-option change. It does not roll back runtime files and is not part of
this update procedure.
