"""Limpeza única autorizada e retenção das 50 tentativas mais recentes."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from . import file_io as safe

LIMIT = 50
POLICY_ID = 'history-50-reset-20261020'
MARKER = 'history-policy.json'


def _roots(package):
    package = safe.source_root(package)
    record = safe.read_json(package/'prepared.json')
    if (not isinstance(record, dict) or record.get('status') != 'prepared'
            or record.get('content_scope') != 'installed_content'):
        raise ValueError('History maintenance requires a prepared launcher package')
    state = package/'launcher'
    safe.check_components(state)
    state.mkdir(exist_ok=True)
    return state, state/'sessions'


def _policy(path):
    safe.check_components(path)
    if not path.exists():
        return None
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size > 4096:
            raise ValueError('Invalid history policy receipt; history was not reset.')
        value = json.load(stream)
    if (not isinstance(value, dict) or value.get('schema_version') != 1
            or value.get('policy_id') != POLICY_ID or value.get('max_sessions') != LIMIT
            or value.get('reset_completed') is not True):
        raise ValueError('Invalid history policy receipt; history was not reset.')
    return value


def _save_policy(path, removed):
    value = dict(schema_version=1, policy_id=POLICY_ID, max_sessions=LIMIT,
                 reset_completed=True, removed_sessions=removed,
                 applied_utc=datetime.now(timezone.utc).isoformat())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                prefix='.history-policy-', suffix='.tmp', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        safe.check_components(path)
        if path.exists():
            raise FileExistsError('History policy already exists')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _order(folder):
    # Session IDs carry UTC creation time, independent of later file edits.
    match = re.fullmatch(r'(\d{8}T\d{6}Z)-[0-9a-f]{8}', folder.name)
    if match:
        try:
            stamp = datetime.strptime(match[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            return int(stamp.timestamp()*1_000_000_000), folder.name
        except ValueError:
            pass
    return folder.stat().st_mtime_ns, folder.name


def _plan_delete(root, folders):
    plan = []
    pending = [(folder, False) for folder in folders]
    while pending:
        path, visited = pending.pop()
        if path == root or not path.is_relative_to(root):
            raise safe.SafetyError('History deletion escaped its sessions directory')
        safe.check_components(path)
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            if not visited:
                pending.append((path, True))
                pending.extend((child, False) for child in path.iterdir())
            else:
                plan.append((path, info))
        else:
            safe.require_reference(info, path)
            plan.append((path, info))
    return plan


def maintain_locked(package, *, reserve=0):
    """Caller holds launcher/active.lock and has no active session.

    Reserve one slot before creating an attempt so an active session never
    needs pruning. The one-time reset receipt lives outside sessions/.
    """
    if type(reserve) is not int or reserve not in (0, 1):
        raise ValueError('Invalid history reservation')
    state, root = _roots(package)
    # Contar conclusões novas antes de remover suas pastas. O marco inicial
    # do contador impede importar o histórico anterior à feature.
    policy = _policy(state/MARKER)
    from . import ai_usage
    usage_ready=True
    try:ai_usage.sync(state/'ai-usage.json')
    except (OSError,ValueError,RuntimeError):usage_ready=False
    safe.check_components(root)
    folders = []
    if root.exists():
        if not root.is_dir():
            raise safe.SafetyError('History sessions path must be a directory')
        for path in root.iterdir():
            safe.check_components(path)
            if not path.is_dir():
                raise safe.SafetyError('Unexpected file in history sessions directory')
            folders.append(path)
    folders.sort(key=_order, reverse=True)
    if not usage_ready:
        # Não bloquear o menu manual nem apagar conclusões ainda não contadas.
        return dict(policy_id=POLICY_ID,max_sessions=LIMIT,reset_performed=False,
                    removed_sessions=0,retained_sessions=len(folders),ai_usage_unavailable=True)
    removed = folders if policy is None else folders[LIMIT-reserve:]
    # Inspect the entire deletion set before removing its first file.
    plan = _plan_delete(root, removed)
    for path, before in plan:
        safe.check_components(path)
        current = path.lstat()
        if (current.st_dev, current.st_ino, current.st_mode) != (before.st_dev, before.st_ino, before.st_mode):
            raise safe.SafetyError('History entry changed during cleanup')
        if stat.S_ISDIR(current.st_mode):
            path.rmdir()
        else:
            safe.require_reference(current, path)
            if safe.signature(current) != safe.signature(before):
                raise safe.SafetyError('History file changed during cleanup')
            path.unlink()
    if policy is None:
        _save_policy(state/MARKER, len(removed))
    return dict(policy_id=POLICY_ID, max_sessions=LIMIT, reset_performed=policy is None,
                removed_sessions=len(removed), retained_sessions=len(folders)-len(removed))


def maintain(package):
    """Apply the policy without opening the menu/game; refuse an active menu."""
    if sys.platform != 'linux':
        raise ValueError('History maintenance requires the Linux package lock')
    import fcntl
    state, _ = _roots(package)
    lock = state/'active.lock'
    safe.check_components(lock)
    if lock.exists():
        safe.require_reference(lock.lstat(), lock)
    with lock.open('a+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()), lock)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Close the launcher before maintaining history.') from error
        return maintain_locked(package)
