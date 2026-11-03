# Community candidates and releases

For the public installation command, read [installation](installation.md). This page covers development and promotion.

This is the maintainer workflow for a local Linux x86_64 candidate. A passing
candidate does not publish files, approve dependency licensing, or establish
physical Steam Deck support. Use the [release checklist](community-release-checklist.md)
to track those separate decisions.

## Source ownership

`ac-deck-dev` owns canonical development; this repository owns the curated
community distribution. Review shared contributions into canonical development
before exporting them back here. Keep the public documentation, policy notices,
gallery and contributor history owned by this repository.

An export manifest identifies selected bytes and their canonical source paths.
Its base commit is provenance: uncommitted bytes must be identified as a working
tree snapshot. Neither a candidate ID nor a commit hash alone identifies all
inputs. Preserve exact source, recipe, SDK, notice and artifact inventories.

## Candidate preparation

Use the versioned delivery controller with an explicitly configured persistent
SDK. Follow [SDK setup](community-sdk.md). Run it on Linux x86_64, including an
explicit WSL Linux shell when developing on Windows. Do not install or upgrade
the SDK as part of a candidate run.

The workflow freezes selected public files into an independent snapshot, tests
them, invokes the existing community builder and validates the resulting
archive and compiled runtime. Machine paths belong in ignored local
configuration. Do not use date-specific scripts from `local/` as the procedure.

Create `local/ciclo-entrega.json` with paths that exist in the same Linux
environment. The interpreter must belong to the inventoried SDK:

```json
{
  "sdk": {
    "python": ["/path/to/persistent-sdk/bin/python3.13"],
    "python_root": "/path/to/persistent-sdk",
    "python_manifest": "/path/to/persistent-sdk.manifest.json",
    "native": "/path/to/regular-native-libraries",
    "font": "/path/to/DejaVuSans.ttf",
    "licenses": "/path/to/sdk-notices"
  },
  "community": {
    "work": "/path/to/persistent-community-work"
  }
}
```

Keep SDK and work directories separate. `community.work` must be on a Linux
filesystem that preserves POSIX file modes, including 0644 and 0755. A WSL
checkout can remain on a Windows drive, but use a suitable Linux work directory
for snapshots, builds, extraction, bootstrap and compiled-check resources.
Preflight tests those modes with an exclusively created temporary file in
the work directory and removes only that file; it refuses an unsupported work
filesystem before building. Plans, logs and stage receipts can remain in the
checkout.

In the public repository, policy
notices default to the checkout root. When preparing from canonical development,
set `community.notices` to the curated public checkout containing `LICENSE`,
`NOTICE` and `THIRD_PARTY_NOTICES.md`; this does not license the private root.
Notice files being present does not establish complete license compliance.

Use the existing reviewed SDK inventory when available. For an SDK that has
been set up and reviewed separately, create a new inventory explicitly:

```sh
/path/to/persistent-sdk/bin/python3.13 -B scripts/ciclo_entrega.py sdk-inventory --output /path/to/new-sdk.manifest.json
```

This setup command uses `sdk.python_root`, refuses to overwrite an existing
inventory and records regular-file hashes/sizes and internal symlink targets.
Point `sdk.python_manifest` at that reviewed file. Capturing current bytes is
not independent evidence of their origin or licensing; do not regenerate an
inventory merely to silence a preflight mismatch. Candidate runs never call
this setup operation automatically.

From the public checkout root, substitute the configured SDK interpreter and
choose a new cycle ID:

```sh
/path/to/persistent-sdk/bin/python3.13 -B scripts/ciclo_entrega.py doctor --community
/path/to/persistent-sdk/bin/python3.13 -B scripts/ciclo_entrega.py plan --community --cycle community-local-01
/path/to/persistent-sdk/bin/python3.13 -B scripts/ciclo_entrega.py resume --cycle community-local-01
/path/to/persistent-sdk/bin/python3.13 -B scripts/ciclo_entrega.py status --cycle community-local-01
```

Community stages are `preflight`, `snapshot`, `test`, `build`, `package` and
`verify`, in that order. The plan and `state.json` live in
`local/work/ciclos/ID/` in the invoking checkout; stage attempts retain their
own logs and receipts. The snapshot/build area lives under `community.work`.
Inspect the final `verify` result in `state.json` for the validation evidence
and artifact paths. This profile has no `apply` or `publish`
stage. A normal candidate run neither mutates Git nor installs into the player's
game. It uses the current reviewed source bytes; it does not require a commit
to prepare a local candidate.

The selected public files and their notices are sufficient for the workflow;
a copy without Git metadata can run with a null local source base. Preserve
its export manifest and exact frozen hashes rather than inventing a commit.
The local source base describes that checkout's Git HEAD when available;
canonical export provenance remains in the export manifest. Each run records
its own archive hash. Reproducing this procedure means producing and validating
an identified candidate from reviewed inputs; byte-identical archives across
different runs are not established by these checks.

Sources and inputs must stay unchanged while a cycle runs. Inspect an existing
cycle before creating another. A failed stage retains its evidence; resume only
after resolving the failure. Changed inputs require a new candidate rather
than editing a successful receipt. Retain the previously validated package.

## Evidence required for a candidate

Keep the plan, logs, durations, stage receipts, frozen source inventory, SDK
inventory, compiled verification and final artifact checks together. Record
failures, skips and reused stages. Reuse requires matching inputs, environment
and output hashes; the presence of an old result file is insufficient.

Stage receipts distinguish input verification before and after execution.
`seconds` measures stage work including postflight; it does not include the
preceding input check. The test result records subprocess time, the builder
records PyInstaller compilation and tar/gzip creation separately, and package
validation has its own duration. Use the command's wall time for the operator's
total wait; do not label the full cycle duration as compiler time.

Verify the package manifest and exact archive contents, payload exclusions,
notices, ELF dependencies and GLIBC limit, informational CLI, bootstrap,
relocation with spaces and packaged resource composition. Compiled checks must
load runtime code from the actual executable archive and reject source fallback.
The compiled probe retains its subprocess/network/device guards. Two named
fixtures that require the test Python interpreter run in the source suite
only; `compiled.json` lists them in `source_process_tests`. The remaining
compiled tests compare and load actual executable CodeType with no source
fallback. Do not count those two process fixtures as compiled execution.

Automated checks use synthetic data and offscreen composition. They do not open
Steam or the game, modify a real installation, or test a physical Deck.

## Corresponding dependency sources

The reviewed source selection and original notice bytes are recorded in
[`licenses/dependency-sources.json`](../licenses/dependency-sources.json).
Use the versioned collector from this public checkout; it does not require
private files or read installed system/SDK notices as hidden inputs:

```sh
python3 -B scripts/preparar_fontes_dependencias.py \
  --manifest licenses/dependency-sources.json \
  --output local/dependency-materials
python3 -B scripts/preparar_fontes_dependencias.py \
  --manifest licenses/dependency-sources.json \
  --output local/dependency-materials --verify-only
python3 -B scripts/preparar_fontes_dependencias.py \
  --manifest licenses/dependency-sources.json \
  --output local/dependency-materials --verify-only \
  --archive local/ac-deck-dependency-sources.tar.gz
```

The collector obtains only pinned HTTPS artifacts and repository-relative
notices, verifies existing files before reuse and refuses divergent bytes.
An archive needs a new output path. It retains the exact inventory bytes and
checks the final archive's member names, sizes and hashes. Source archives,
patches and build recipes remain separate from the runtime; do not install
them over the launcher or include binary packages used only as provenance
evidence. See [source collection and coverage](dependency-sources.md).

Record the source-archive checksum and its inventory identity in the release
record, and provide equivalent recipient access when publishing. Successful
collection proves the recorded material is present. Compatibility of license
terms, static components, notices and replacement/relink requirements remain
part of the [dependency review](dependency-license-review.md).

## Version and promotion

Use a unique local candidate ID for each distinct input set. Assign a public
version only when preparing a reviewed release, for example `v0.1.0-rc.1` for
a preview or `v0.1.0` for a supported release. These are naming examples, not
versions currently approved for publication. Never reuse a published version
for different bytes.

Promotion is a separate review of an existing immutable candidate:

1. Freeze the candidate archive and bootstrap hashes, source inventory, SDK
   inventory, validation receipts, notices and dependency-source artifacts.
   Identify the prior release and the proposed update/rollback compatibility.
2. Prepare matching public sources for review. Before publication, the release
   record must identify the public source commit and match its selected bytes
   to the frozen candidate. If committing changes only documentation, retain
   the candidate after verifying that its build inputs still match. If any
   build input changed, create and validate another candidate.
3. Close the applicable [dependency review](dependency-license-review.md),
   redistribution and source/history/privacy checks. Include corresponding
   dependency sources and required notices for the actual binaries. An older
   preview's source archive does not cover a newer SDK by inference.
4. A supported release requires the [physical Deck checks](deck-validation-plan.md)
   for the exact archive. An explicitly experimental preview may be published
   after its automated and distribution checks, with physical installation,
   races, compatibility and performance recorded as untested. Do not invent
   tested SteamOS/Proton versions or acceptance. The current preview follows
   this experimental route under the user's explicit publication authorization.
5. Present the release record, exact destination, source diff, package,
   dependency sources, checksums, installation/update instructions, known
   limits and rollback target. Obtain explicit publication authorization if
   the session has not already provided it. Existing explicit authorization
   applies to the reviewed result; implementation/build approval alone does
   not grant publication. The current session explicitly authorized the
   public commit, push and installation release.
6. After authorization, publish the reviewed sources and those same artifact
   bytes to the approved destination. Verify the remote source identity and
   download hashes before adding a working download command to the README.
   Do not rebuild the executable during promotion or overwrite an older asset.

Keep a release record with these fields in the release's evidence, outside
runtime policy or agent instructions:

| Field | Required value |
| --- | --- |
| Version and candidate | Unique version, local cycle ID and intended channel |
| Sources | Public source commit, canonical base provenance, frozen source inventory SHA-256 and working-tree status at build time |
| Inputs and checks | SDK/recipe inventory hashes, validation receipt hashes, failures/skips and remaining limits |
| Downloads | Exact runtime archive, bootstrap and dependency-source filenames, byte sizes and SHA-256 values |
| Licenses | Reviewed component inventory, notices and corresponding-source/build material |
| Deck result | Hardware, SteamOS, Proton, tested archive hash, scenarios and acceptance |
| Update and recovery | Supported prior versions, data compatibility, preserved data and previous verified version/hash |
| Authorization and publication | User's approved scope, approval reference, actual source/tag/download locations and verified remote hashes |

A locally prepared record is not evidence that its approval, publication or
Deck fields have happened. Leave pending fields explicit.

## Withdrawal and rollback

Keep each published package, its sources, notices, checksums and validation
record available by version. Retain the previous verified package while testing
a replacement. A failed local candidate does not replace any published version.

For a published defect, stop recommending the affected version and describe
the defect and affected update range. Changing the recommended download or
publishing a corrective release requires the user's authorization. Keep the
original version identity and evidence; do not silently replace its assets.

Rollback uses the previous verified runtime and the compatibility procedure
recorded for that version. Close the launcher and game normally first. Preserve
current player data and the failed installation for diagnosis. Restore only
distribution-owned files; do not delete the game, Proton prefix, Steam data or
unknown files. Do not restore an older progress backup over newer progress.
If a data migration is incompatible with the prior runtime, stop and use the
release's reviewed recovery procedure rather than forcing older binaries.

`ac-deck restore-steam` restores only its recorded, still-unchanged launch
option. It does not undo CSP installation or roll back the runtime or player
data. Validate those paths separately. The public source utility in
[updates and recovery](update-and-recovery.md) has passed isolated packaging
updates and rollback with unchanged product/Python identities. Physical Deck
support and functional data migrations remain separate release gates.
