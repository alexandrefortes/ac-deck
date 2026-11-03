#!/usr/bin/env python3
"""Update packaging of an owned community installation; never change player data."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import install_ac_deck as bootstrap
from scripts.ciclo_entrega_lib.common import (atomic_json, digest, file_state, locked,
                                             read_json, sync_directory)
from src.launcher import file_io as safe, steam_install_options

PROFILE = 'community-packaging-v1'
TOP_FILES = {'ac-deck', 'build-info.json', 'LEIA-ME.txt', 'LICENSE', 'NOTICE',
             'THIRD_PARTY_NOTICES.md', 'manifest.json'}


def managed(name):
    canonical = safe.relative_file(name)
    if canonical != name or not (name in TOP_FILES or name.startswith(('_internal/', 'licenses/'))):
        raise ValueError('Unsupported managed distribution path: '+str(name))
    return name


def target_path(root, name):
    path = root
    for part in managed(name).split('/'):
        if path.exists():
            if not path.is_dir():
                raise ValueError('A file occupies a distribution directory: '+str(path))
            if any(p.name.casefold() == part.casefold() and p.name != part for p in path.iterdir()):
                raise ValueError('Case collision in distribution path: '+str(path/part))
        path /= part
        safe.check_components(path)
    return path


def release(root, *, strict):
    document, manifest_sha = safe.read_document(root/'manifest.json')
    if not isinstance(document.get('files'), list):
        raise ValueError('Community manifest must contain a files array')
    rows = {}
    for row in document['files']:
        if not isinstance(row, dict) or not isinstance(row.get('path'), str):
            raise ValueError('Invalid community manifest row')
        name = managed(row['path'])
        if (name == 'manifest.json' or name.casefold() in {n.casefold() for n in rows}
                or not isinstance(row.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
                or type(row.get('size_bytes')) is not int or row['size_bytes'] < 0):
            raise ValueError('Invalid or duplicate community manifest row')
        path = target_path(root, name)
        state = file_state(path)
        if not state or state['sha256'] != row['sha256'] or state['size'] != row['size_bytes']:
            raise ValueError('Managed distribution file was changed: '+name)
        if state['mode'] not in (0o644, 0o755):
            raise ValueError('Distribution requires a Linux filesystem preserving POSIX modes')
        rows[name] = state
    required = {'ac-deck', 'build-info.json', 'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'}
    if not required <= rows.keys() or rows['ac-deck']['mode'] != 0o755:
        raise ValueError('Unsupported older preview: missing current community ownership contract')
    rows['manifest.json'] = file_state(root/'manifest.json')
    if rows['manifest.json']['sha256'] != manifest_sha or rows['manifest.json']['mode'] != 0o644:
        raise ValueError('Community manifest changed or has an unsupported mode')
    if strict and set(bootstrap._inventory(root)[1]) != set(rows):
        raise ValueError('Community archive contains missing or extra files')
    info = safe.read_json(root/'build-info.json')
    if (info.get('schema_version') != 1 or info.get('distribution') != 'community'
            or info.get('architecture') != 'x86_64' or info.get('public_name') != 'ac-deck'
            or any(info.get(k) is not None for k in ('csp', 'csp_fonts', 'gt5_camera', 'bacc_cameras',
                    'rogue_toasty_assets', 'rogue_album_assets', 'reused_payload_manifest'))):
        raise ValueError('Unsupported older preview or private distribution')
    sources = info.get('source_sha256', {})
    if (not isinstance(sources, dict) or any(not isinstance(name, str) or safe.relative_file(name) != name
            or not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
            for name,value in sources.items())):
        raise ValueError('Distribution source identity is invalid')
    runtime = {name:value for name,value in sources.items()
               if name.startswith('src/launcher/') or name in ('scripts/jogo_deck.py', 'scripts/pratica_deck.py')}
    if not {'src/launcher/community_install.py', 'src/launcher/application.py',
            'scripts/jogo_deck.py'} <= runtime.keys() or not isinstance(info.get('python'), str):
        raise ValueError('Unsupported older preview: runtime/data layout identity is missing')
    return dict(files=rows, identity=dict(profile=PROFILE, python=info['python'],
                architecture=info['architecture'], runtime_sources=runtime))


def copy(source, destination, wanted):
    safe.copy_verified(source, destination, wanted['sha256'])
    copied, verified = safe.hash_reference_file(destination)
    if copied != wanted['sha256'] or verified.st_size != wanted['size']:
        raise ValueError('Temporary copy changed before mode update')
    stream, opened = safe.open_reference(destination)
    with stream:
        if safe.signature(verified) != safe.signature(opened) or verified.st_mode != opened.st_mode:
            raise ValueError('Temporary copy identity changed before mode update')
        os.fchmod(stream.fileno(), wanted['mode'])
        os.fsync(stream.fileno())
    if file_state(destination) != wanted:
        raise ValueError('Copied bytes or mode differ: '+str(destination))
    sync_directory(destination.parent)


def durable(root, files):
    directories = {root}
    for name in files:
        path = target_path(root, name)
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
        directories.update(parent for parent in path.parents if parent == root or parent.is_relative_to(root))
    for directory in sorted(directories, key=lambda p:len(p.parts), reverse=True):
        sync_directory(directory)
    sync_directory(root.parent)


def stage(archive, sha256, directory):
    directory.mkdir()
    saved = directory/'archive.tar.gz'
    bootstrap._stage_archive(archive, None, saved, sha256)
    with saved.open('rb') as stream:
        os.fsync(stream.fileno())
    sync_directory(directory)
    bootstrap._extract_archive(saved, directory)
    root = directory/bootstrap.ROOT_NAME
    result = release(root, strict=True)
    durable(root, result['files'])
    return root, result


def closed(confirmed):
    if not confirmed:
        raise ValueError('Close Steam, the launcher and the game, then pass --closed')
    steam_install_options._steam_closed()


def storage(destination):
    target = safe.source_root(bootstrap._absolute(destination))
    home = target/'local/distribution-update'
    safe.check_components(home)
    return target, home


def own_storage(target, home):
    owner = home/'owner.json'
    expected = dict(schema=1, profile=PROFILE, target=str(target))
    if owner.exists():
        if read_json(owner) != expected:
            raise ValueError('Update storage belongs to another installation or contract')
    else:
        if home.exists() and any(home.iterdir()):
            raise ValueError('Unknown update storage was preserved; do not overwrite it')
        home.mkdir(parents=True, exist_ok=True)
        safe.write_json(owner, expected)
        with owner.open('rb') as stream:
            os.fsync(stream.fileno())
        sync_directory(home)
        sync_directory(home.parent)
        sync_directory(target)


def receipt(plan, direction):
    key = 'new' if direction == 'update' else 'old'
    return dict(schema=1, profile=PROFILE, transaction=plan['id'], direction=direction,
                files=plan[key]['files'], identity=plan[key]['identity'],
                archive_sha256=plan[key]['archive_sha256'])


def validate_rows(rows):
    if not isinstance(rows, dict) or not TOP_FILES.intersection(rows) or 'manifest.json' not in rows:
        raise ValueError('Update journal file selection is invalid')
    for name, row in rows.items():
        managed(name)
        if (not isinstance(row, dict) or not isinstance(row.get('sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
                or type(row.get('size')) is not int or row['size'] < 0 or row.get('mode') not in (0o644, 0o755)):
            raise ValueError('Update journal file identity is invalid')


def load(target, home):
    state = read_json(home/'active.json')
    token = state.get('id', '') if isinstance(state, dict) else None
    if (not isinstance(state, dict) or state.get('schema') != 1 or state.get('target') != str(target)
            or not isinstance(token, str) or not re.fullmatch('[0-9a-f]{32}', token)
            or state.get('direction') not in ('update', 'rollback')):
        raise ValueError('Update journal does not belong to this installation')
    transaction = home/'transactions'/token
    plan = read_json(transaction/'plan.json')
    if (not isinstance(plan, dict) or plan.get('schema') != 1 or plan.get('id') != token or plan.get('target') != str(target)
            or digest(plan) != state.get('plan_sha256')):
        raise ValueError('Update plan changed; preserve the journal and backups')
    for key, directory in (('old', 'before'), ('new', 'after')):
        if not isinstance(plan.get(key), dict):
            raise ValueError('Update plan release identity is invalid')
        validate_rows(plan[key]['files'])
        observed = release(transaction/directory/bootstrap.ROOT_NAME, strict=True)
        if observed != {name:plan[key][name] for name in ('files', 'identity')}:
            raise ValueError('Frozen update input or backup changed')
        if not isinstance(plan[key]['archive_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', plan[key]['archive_sha256']):
            raise ValueError('Recorded archive identity is invalid')
        archive = transaction/directory/'archive.tar.gz'
        if plan[key].get('archive_stored', directory == 'after') or archive.exists():
            archived = file_state(archive)
            if not archived or archived['sha256'] != plan[key]['archive_sha256']:
                raise ValueError('Saved update archive changed or is missing')
    if plan['old']['identity'] != plan['new']['identity']:
        raise ValueError('Runtime/Python/data layout differs; a reviewed migration contract is required')
    return state, plan, transaction


def apply(target, home, state, plan, transaction):
    direction = state['direction']
    before, after = (plan['old'], plan['new']) if direction == 'update' else (plan['new'], plan['old'])
    source = transaction/('after' if direction == 'update' else 'before')/bootstrap.ROOT_NAME
    names = sorted(set(before['files']) | set(after['files']))
    def observed(name):
        return file_state(target_path(target, name))
    def reconcile():
        for name in names:
            if observed(name) not in (before['files'].get(name), after['files'].get(name)):
                raise ValueError('Managed file diverges from old/new journal states: '+name)
    reconcile()
    marker = home/'installed.json'
    marker_before = file_state(marker)
    if marker.exists():
        current = read_json(marker)
        allowed = [receipt(plan, direction), plan.get('previous_receipt')]
        if direction == 'rollback':
            allowed.append(receipt(plan, 'update'))
        if current not in allowed:
            raise ValueError('Installed ownership receipt changed; preserve it')
    if state.get('complete'):
        if any(observed(name) != after['files'].get(name) for name in names):
            raise ValueError('Completed distribution or receipt changed; no repair was performed')
        if marker.exists():
            if read_json(marker) != receipt(plan, direction):
                raise ValueError('Completed distribution or receipt changed; no repair was performed')
        else:
            if file_state(marker) is not None or load(target, home)[0] != state:
                raise ValueError('Ownership metadata changed during reconciliation')
            atomic_json(marker, receipt(plan, direction))
        return dict(status='complete', direction=direction, destination=str(target), transaction=plan['id'],
                    manifest_sha256=after['files']['manifest.json']['sha256'], player_data_changed=False)
    closed(True)
    for name in [n for n in names if n != 'manifest.json']+['manifest.json']:
        path = target_path(target, name)
        old, wanted = before['files'].get(name), after['files'].get(name)
        current = observed(name)
        if current == wanted:
            continue
        if current != old:
            raise ValueError('Destination changed during update: '+name)
        if wanted is None:
            if observed(name) != current:
                raise ValueError('Destination changed before deletion: '+name)
            path.unlink()
            sync_directory(path.parent)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name('.ac-deck-update-'+uuid.uuid4().hex+'.new')
            copy(source/name, temporary, wanted)
            if observed(name) != current:
                raise ValueError('Destination changed during copy; both files were preserved: '+name)
            temporary.replace(path)
            sync_directory(path.parent)
    durable(target, after['files'])
    # Check the frozen source again before publishing the ownership receipt.
    if load(target, home)[0] != state:
        raise ValueError('Active journal changed during update')
    for name in names:
        if observed(name) != after['files'].get(name):
            raise ValueError('Distribution changed before final confirmation: '+name)
    if file_state(marker) != marker_before:
        raise ValueError('Installed ownership receipt changed during update')
    atomic_json(marker, receipt(plan, direction))
    state['complete'] = True
    atomic_json(transaction/(direction+'.json'), state)
    atomic_json(home/'active.json', state)
    return dict(status='complete', direction=direction, destination=str(target), transaction=plan['id'],
                manifest_sha256=after['files']['manifest.json']['sha256'], player_data_changed=False)


def update(*, archive, sha256, destination, current_archive=None, current_sha256=None, confirmed=False):
    closed(confirmed)
    target, home = storage(destination)
    own_storage(target, home)
    with locked(home/'update.lock'):
        if (home/'active.json').exists():
            if not load(target, home)[0].get('complete'):
                raise ValueError('An update is incomplete; use resume with the same destination')
        marker = home/'installed.json'
        previous = read_json(marker) if marker.exists() else None
        if previous is None and (current_archive is None or current_sha256 is None):
            raise ValueError('First adoption requires --current-archive and --current-sha256; older previews are not assumed owned')
        if previous is not None and (current_archive is not None or current_sha256 is not None):
            raise ValueError('An ownership receipt already exists; do not replace its anchor')
        token = uuid.uuid4().hex
        transaction = home/'transactions'/token
        transaction.mkdir(parents=True)
        sync_directory(transaction.parent)
        sync_directory(home)
        _, new = stage(archive, sha256, transaction/'after')
        new['archive_sha256'] = sha256.lower()
        new['archive_stored'] = True
        if previous is None:
            _, old = stage(current_archive, current_sha256, transaction/'before')
            old['archive_sha256'] = current_sha256.lower()
            old['archive_stored'] = True
        else:
            if not isinstance(previous, dict) or previous.get('schema') != 1 or previous.get('profile') != PROFILE:
                raise ValueError('Unsupported ownership receipt')
            old = {key:previous[key] for key in ('files', 'identity', 'archive_sha256')}
            old['archive_stored'] = False
            validate_rows(old['files'])
        if old['identity'] != new['identity']:
            raise ValueError('Runtime/Python/data layout differs; update requires a reviewed migration contract')
        for name, wanted in old['files'].items():
            if file_state(target_path(target, name)) != wanted:
                raise ValueError('Installed managed file was locally edited: '+name)
        for name in set(new['files'])-set(old['files']):
            if target_path(target, name).exists():
                raise ValueError('Unknown file occupies the new distribution path: '+name)
        if previous is not None:
            backup = transaction/'before'/bootstrap.ROOT_NAME
            backup.mkdir(parents=True)
            for name, wanted in old['files'].items():
                copy(target_path(target, name), backup/name, wanted)
            if release(backup, strict=True) != {key:old[key] for key in ('files', 'identity')}:
                raise ValueError('Backup does not match the installed ownership receipt')
            durable(backup, old['files'])
        plan = dict(schema=1, id=token, target=str(target), old=old, new=new, previous_receipt=previous)
        atomic_json(transaction/'plan.json', plan)
        state = dict(schema=1, id=token, target=str(target), direction='update',
                     plan_sha256=digest(plan), complete=False)
        atomic_json(home/'active.json', state)
        load(target, home)
        return apply(target, home, state, plan, transaction)


def recover(*, destination, rollback=False, confirmed=False):
    closed(confirmed)
    target, home = storage(destination)
    own_storage(target, home)
    with locked(home/'update.lock'):
        state, plan, transaction = load(target, home)
        if rollback and state['direction'] == 'update':
            if not state.get('complete'):
                raise ValueError('Finish the interrupted update with resume before requesting rollback')
            for name, wanted in plan['new']['files'].items():
                if file_state(target_path(target, name)) != wanted:
                    raise ValueError('Current managed runtime was locally edited; rollback refused: '+name)
            state = dict(state, direction='rollback', complete=False)
            atomic_json(home/'active.json', state)
        return apply(target, home, state, plan, transaction)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('update', 'resume', 'rollback'):
        command = commands.add_parser(name)
        command.add_argument('--destination', type=Path, required=True)
        command.add_argument('--closed', action='store_true')
        if name == 'update':
            command.add_argument('--archive', type=Path, required=True)
            command.add_argument('--sha256', required=True)
            command.add_argument('--current-archive', type=Path)
            command.add_argument('--current-sha256')
    args = parser.parse_args(argv)
    try:
        if args.command == 'update':
            result = update(archive=args.archive, sha256=args.sha256, destination=args.destination,
                            current_archive=args.current_archive, current_sha256=args.current_sha256,
                            confirmed=args.closed)
        else:
            result = recover(destination=args.destination, rollback=args.command == 'rollback', confirmed=args.closed)
        print(json.dumps(result))
    except (OSError, ValueError, RuntimeError, KeyError, bootstrap.tarfile.TarError) as exc:
        print('Update stopped: '+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
