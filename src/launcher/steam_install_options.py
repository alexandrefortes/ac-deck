"""Conservative, reversible edits to one explicitly selected Steam account.

Steam must remain closed throughout the operation. The process check and
pre-rename comparison cannot lock Steam or prevent another writer racing us.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import uuid

from . import file_io as safe, install_discovery


class OptionsError(ValueError):
    pass


class ProcessesRunning(OptionsError):
    pass


PATH = ('userlocalconfigstore', 'software', 'valve', 'steam', 'apps', '244210')
INSERT_PREFIX = b'\n\t\t"LaunchOptions"\t'
INSERT_SUFFIX = b'\n'
APP_PREFIX = b'\n\t"244210" {' + INSERT_PREFIX
APP_SUFFIX = INSERT_SUFFIX + b'\t}\n'


def _decode(token):
    raw = token[1:-1].decode('utf-8')
    result = []
    i = 0
    while i < len(raw):
        if raw[i] == '\\':
            i += 1
            if i == len(raw) or raw[i] not in '\\"nrt':
                raise OptionsError('Unsupported VDF escape')
            result.append({'n': '\n', 'r': '\r', 't': '\t'}.get(raw[i], raw[i]))
        else:
            result.append(raw[i])
        i += 1
    return ''.join(result)


def _quote(value):
    if any(c in value for c in '\x00\r\n'):
        raise OptionsError('Invalid launch option')
    return ('"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"').encode('utf-8')


def _tokens(data):
    if len(data) > 8 * 1024 * 1024 or b'\x00' in data:
        raise OptionsError('Unsupported VDF')
    data.decode('utf-8-sig')
    result, i = [], 3 if data.startswith(b'\xef\xbb\xbf') else 0
    while i < len(data):
        start = i
        if data[i:i+1] in b' \t\r\n':
            i += 1
        elif data[i:i+2] == b'//':
            end = data.find(b'\n', i)
            i = len(data) if end < 0 else end + 1
        elif data[i:i+1] in (b'{', b'}'):
            result.append((data[i:i+1], i, i+1))
            i += 1
        elif data[i] == 34:
            i += 1
            while i < len(data) and data[i] != 34:
                if data[i] == 92:
                    i += 1
                i += 1
            if i >= len(data):
                raise OptionsError('Unterminated VDF string')
            i += 1
            result.append((b's', start, i))
        else:
            raise OptionsError('Unsupported VDF syntax')
    return result


def _locate(data):
    tokens = _tokens(data)
    index, apps_end, app_end, option = 0, [], [], []

    def obj(prefix, nested=False):
        nonlocal index
        if len(prefix) > 64:
            raise OptionsError('VDF nesting too deep')
        seen = set()
        while index < len(tokens):
            kind, start, end = tokens[index]
            if kind == b'}':
                if not nested:
                    raise OptionsError('Unexpected VDF close')
                if prefix == PATH:
                    app_end.append(start)
                elif prefix == PATH[:-1]:
                    apps_end.append(start)
                index += 1
                return
            if kind != b's':
                raise OptionsError('Invalid VDF key')
            key = _decode(data[start:end]).casefold()
            path = prefix + (key,)
            relevant = PATH[:len(path)] == path or path == PATH + ('launchoptions',)
            if relevant and key in seen:
                raise OptionsError('Duplicate VDF path')
            seen.add(key)
            key_start = start
            index += 1
            if index >= len(tokens):
                raise OptionsError('Missing VDF value')
            kind, start, end = tokens[index]
            index += 1
            if kind == b'{':
                if path == PATH + ('launchoptions',):
                    raise OptionsError('LaunchOptions is not a value')
                obj(path, True)
            elif kind == b's':
                if path == PATH + ('launchoptions',):
                    option.append((key_start, start, end, _decode(data[start:end])))
                elif path in (PATH, PATH[:-1]):
                    raise OptionsError('App entry is not an object')
            else:
                raise OptionsError('Invalid VDF value')
        if nested:
            raise OptionsError('Incomplete VDF object')

    obj(())
    if len(apps_end) != 1 or len(app_end) > 1 or len(option) > 1:
        raise OptionsError('Apps entry missing or ambiguous')
    return apps_end[0], app_end[0] if app_end else None, option[0] if option else None


def _steam_closed():
    if sys.platform != 'linux':
        raise OptionsError('Steam configuration requires Linux')
    try:
        ancestors = set()
        pid = os.getpid()
        while pid > 0 and pid not in ancestors:
            ancestors.add(pid)
            status = (Path('/proc')/str(pid)/'status').read_text()
            match = re.search(r'^PPid:\s*(\d+)\s*$', status, re.MULTILINE)
            if not match:
                raise OptionsError('Cannot verify installer process ancestry')
            pid = int(match.group(1))
        entries = list(Path('/proc').iterdir())
        for entry in entries:
            if not entry.name.isdecimal():
                continue
            try:
                if entry.stat().st_uid != os.getuid():
                    continue
                name = (entry/'comm').read_text().strip().casefold()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if name.startswith('steam') or (name in {'acs.exe', 'assettocorsa.exe', 'ac-deck', 'papao'}
                                              and int(entry.name) not in ancestors):
                raise ProcessesRunning('Close Steam, Assetto Corsa and the launcher, then run the same command again')
    except PermissionError as exc:
        raise OptionsError('Cannot verify process state') from exc


def _read(path):
    stream, info = safe.open_reference(path)
    if hasattr(os, 'getuid') and info.st_uid != os.getuid():
        stream.close()
        raise OptionsError('File is owned by another user')
    with stream:
        data = stream.read(8 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    safe.require_reference(after, path)
    if len(data) > 8 * 1024 * 1024:
        raise OptionsError('File is too large')
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    if safe.signature(info) != safe.signature(after) or safe.signature(info) != safe.signature(current):
        raise OptionsError('File changed while reading')
    return data, info


def _sync_directory(path):
    directory = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _replace(path, before, info, after):
    temp = path.with_name(path.name + '.ac-deck-' + uuid.uuid4().hex)
    safe.check_components(temp)
    if info.st_mode & 0o7000:
        raise OptionsError('Steam configuration has special permission bits; preserve it')
    if sys.platform == 'linux' and os.listxattr(path, follow_symlinks=False):
        raise OptionsError('Steam configuration has extended attributes; preserve it')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, info.st_mode & 0o777)
    try:
        with os.fdopen(fd, 'wb') as out:
            if sys.platform == 'linux':
                os.fchmod(out.fileno(), info.st_mode & 0o777)
                if os.fstat(out.fileno()).st_gid != info.st_gid:
                    raise OptionsError('Cannot preserve Steam configuration group')
            out.write(after)
            out.flush()
            os.fsync(out.fileno())
        _steam_closed()
        current, actual = _read(path)
        if current != before or safe.signature(actual) != safe.signature(info):
            raise OptionsError('Steam configuration changed; preserved')
        os.replace(temp, path)
        _sync_directory(path.parent)
        if _read(path)[0] != after:
            raise OptionsError('Steam configuration readback differs')
    finally:
        if temp.exists():
            temp.unlink()


def _target(root, account):
    root = safe.source_root(root)
    if not isinstance(account, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', account) or int(account) >= 2**32:
        raise OptionsError('Select an explicit Steam account ID')
    target = root/'userdata'/account/'config'/'localconfig.vdf'
    safe.check_components(target)
    return root, target


def discover_accounts(root):
    """List account IDs with regular local config files; never choose one."""
    root = safe.source_root(root)
    userdata = root/'userdata'
    safe.check_components(userdata)
    if not userdata.is_dir():
        raise OptionsError('Steam userdata directory is missing')
    result = []
    for child in userdata.iterdir():
        if not re.fullmatch(r'[1-9][0-9]{0,9}', child.name) or int(child.name) >= 2**32:
            continue
        _, path = _target(root, child.name)
        if path.exists():
            safe.require_reference(path.lstat(), path)
            result.append(child.name)
    return sorted(result, key=int)


def preferred_account(root, accounts):
    """Use Steam's unique most recent login only when its local config exists."""
    root = safe.source_root(root)
    path = root / 'config/loginusers.vdf'
    safe.check_components(path)
    if not path.exists():
        return None
    users = install_discovery._read_vdf(path).get('users')
    if not isinstance(users, dict):
        raise OptionsError('Steam login metadata has no users object')
    recent = [steam_id for steam_id, record in users.items()
              if isinstance(record, dict) and record.get('mostrecent') == '1']
    if len(recent) != 1 or not re.fullmatch(r'[0-9]{17}', recent[0]):
        return None
    account = str(int(recent[0]) - 76561197960265728)
    return account if account in accounts else None


def _arg(path):
    if not Path(path).is_absolute():
        raise OptionsError('Path must be absolute')
    path = safe.absolute(path)
    text = str(path)
    if not path.is_absolute() or '%command%' in text.casefold() or any(c in text for c in '\\"$`\x00\r\n'):
        raise OptionsError('Path cannot be represented safely')
    return '"' + text + '"'


def _receipt(path, target, account):
    raw, info = _read(path)
    if sys.platform == 'linux' and info.st_mode & 0o077:
        raise OptionsError('Receipt must be private')
    record = json.loads(raw.decode('utf-8'))
    if (not isinstance(record, dict) or record.get('schema_version') != 1
            or record.get('target') != str(target) or record.get('account') != account
            or type(record.get('inserted')) is not bool or type(record.get('inserted_app')) is not bool
            or type(record.get('adopted', False)) is not bool
            or record['inserted_app'] and not record['inserted']
            or any(not isinstance(record.get(k), str) or not re.fullmatch('[0-9a-f]{64}', record[k])
                   for k in ('before_sha256', 'after_sha256'))):
        raise OptionsError('Receipt does not match selected account')
    try:
        old = base64.b64decode(record['original'], validate=True)
        token = base64.b64decode(record['installed'], validate=True)
    except (KeyError, ValueError) as exc:
        raise OptionsError('Invalid receipt') from exc
    if (len(token) < 2
            or not token.startswith(b'"') or not token.endswith(b'"')):
        raise OptionsError('Invalid receipt values')
    _decode(token)
    if record.get('adopted'):
        if (record['inserted'] or old != token
                or record['before_sha256'] != record['after_sha256']):
            raise OptionsError('Invalid adopted launch option receipt')
    elif record['inserted']:
        if old:
            raise OptionsError('Invalid receipt values')
    else:
        if len(old) < 2 or not old.startswith(b'"') or not old.endswith(b'"'):
            raise OptionsError('Invalid original launch option')
        _environment_prefix(_decode(old))
    return record, old, token


def _environment_prefix(value):
    """Preserve literal environment assignments without accepting shell code."""
    if not value:
        return ''
    message = ('Existing Steam launch options were preserved. Automatic setup supports only '
               'literal NAME=value assignments followed by %command%; remove custom wrappers before retrying.')
    if any(char in value for char in '$`\x00\r\n'):
        raise OptionsError(message)
    value = value.strip()
    word = r'''(?:[^\s'"\\$`();<>|&~{}]|'[^']*'|"(?:[^"\\]|\\.)*"|\\[^\r\n])*'''
    if value.count('%command%') != 1 or not re.fullmatch(
            r'(?:[A-Za-z_][A-Za-z0-9_]*=' + word + r'[ \t]+)*%command%', value):
        raise OptionsError(message)
    try:
        parser = shlex.shlex(value, posix=True, punctuation_chars='();<>|&')
        parser.whitespace_split = True
        parser.commenters = ''
        tokens = list(parser)
    except ValueError as error:
        raise OptionsError(message) from error
    if not tokens or tokens[-1] != '%command%':
        raise OptionsError(message)
    assignments = []
    for token in tokens[:-1]:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', token):
            raise OptionsError(message)
        name, literal = token.split('=', 1)
        assignments.append(name + '=' + shlex.quote(literal))
    return ' '.join(assignments) + (' ' if assignments else '')


def _plan(data, token):
    apps_end, end, option = _locate(data)
    if option:
        _environment_prefix(option[3])
    inserted_app = end is None
    if option:
        _, start, stop, _ = option
        old = data[start:stop]
        updated = data[:start] + token + data[stop:]
        inserted = False
    elif inserted_app:
        old = b''
        updated = data[:apps_end] + APP_PREFIX + token + APP_SUFFIX + data[apps_end:]
        inserted = True
    else:
        old = b''
        updated = data[:end] + INSERT_PREFIX + token + INSERT_SUFFIX + data[end:]
        inserted = True
    _, _, check = _locate(updated)
    if check is None or check[3] != _decode(token):
        raise OptionsError('VDF round trip failed')
    return updated, old, inserted, inserted_app


def install(root, account, receipt, launcher, package, *, csp_payload=None, steam_closed_confirmed=False):
    if not steam_closed_confirmed:
        raise OptionsError('Confirm Steam is closed for the entire operation')
    _steam_closed()
    root, path = _target(root, account)
    receipt = safe.absolute(receipt)
    safe.check_components(receipt)
    if safe.inside(receipt, root) or not receipt.parent.is_dir():
        raise OptionsError('Receipt must be in an existing private folder outside Steam')
    for item in (launcher, package):
        safe.check_components(safe.absolute(item))
    if not safe.absolute(launcher).is_file() or not safe.absolute(package).is_dir():
        raise OptionsError('Launcher or package is missing')
    command = _arg(launcher) + ' steam --pacote ' + _arg(package)
    if csp_payload is not None:
        safe.check_components(safe.absolute(csp_payload))
        manifest = safe.absolute(csp_payload)/'manifest.json'
        safe.check_components(manifest)
        if not manifest.is_file():
            raise OptionsError('Prepared CSP payload is missing')
        safe.require_reference(manifest.lstat(), manifest)
        command += ' --kit-csp ' + _arg(csp_payload)
    command += ' -- %command%'
    data, info = _read(path)
    if receipt.exists():
        record, old, recorded_token = _receipt(receipt, path, account)
        prefix = '' if record['inserted'] or record.get('adopted') else _environment_prefix(_decode(old))
        token = _quote(prefix + command)
        if recorded_token != token:
            raise OptionsError('Receipt belongs to a different launcher command')
        _, _, current = _locate(data)
        if current and data[current[1]:current[2]] == token:
            key, _, stop, _ = current
            if record['inserted_app']:
                _, app_end, _ = _locate(data)
                a = key - len(APP_PREFIX) + len(b'"LaunchOptions"\t')
                if a < 0 or data[a:app_end+2] != APP_PREFIX + token + APP_SUFFIX:
                    raise OptionsError('Installed app entry changed; preserved')
            elif record['inserted']:
                if key < 3 or data[key-3:stop+1] != INSERT_PREFIX + token + INSERT_SUFFIX:
                    raise OptionsError('Installed launch option changed; preserved')
            return record
        if hashlib.sha256(data).hexdigest() != record['before_sha256']:
            raise OptionsError('Steam configuration changed since the receipt; preserved')
        updated, old_again, inserted, inserted_app = _plan(data, token)
        if (old_again != old or inserted != record['inserted'] or inserted_app != record['inserted_app']
                or hashlib.sha256(updated).hexdigest() != record['after_sha256']):
            raise OptionsError('Receipt cannot safely resume this operation')
        _replace(path, data, info, updated)
        return record
    _, _, option = _locate(data)
    adopted = option is not None and option[3] == command
    prefix = _environment_prefix(option[3]) if option and not adopted else ''
    token = _quote(prefix + command)
    if adopted:
        updated, old, inserted, inserted_app = data, token, False, False
    else:
        updated, old, inserted, inserted_app = _plan(data, token)
    record = dict(schema_version=1, account=account, target=str(path), inserted=inserted, inserted_app=inserted_app,
                  original=base64.b64encode(old).decode(), installed=base64.b64encode(token).decode(),
                  before_sha256=hashlib.sha256(data).hexdigest(), after_sha256=hashlib.sha256(updated).hexdigest())
    if adopted:
        record['adopted'] = True
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as output:
        if sys.platform == 'linux':
            os.fchmod(output.fileno(), 0o600)
        json.dump(record, output, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    _sync_directory(receipt.parent)
    if not adopted:
        _replace(path, data, info, updated)
    return record


def restore(root, account, receipt, *, steam_closed_confirmed=False):
    if not steam_closed_confirmed:
        raise OptionsError('Confirm Steam is closed for the entire operation')
    _steam_closed()
    root, path = _target(root, account)
    receipt = safe.absolute(receipt)
    if safe.inside(receipt, root):
        raise OptionsError('Receipt must be outside Steam')
    record, old, token = _receipt(receipt, path, account)
    if record.get('adopted'):
        return
    data, info = _read(path)
    _, app_end, option = _locate(data)
    if hashlib.sha256(data).hexdigest() == record['before_sha256']:
        return
    if option is None:
        raise OptionsError('Installed launch option is missing; preserved')
    key, start, stop, _ = option
    if data[start:stop] != token:
        raise OptionsError('Launch option changed; preserved')
    if record.get('inserted_app'):
        addition = APP_PREFIX + token + APP_SUFFIX
        a = key - len(APP_PREFIX) + len(b'"LaunchOptions"\t')
        b = app_end + len(b'}\n')
        if a < 0 or data[a:b] != addition or old:
            raise OptionsError('Inserted app entry changed; preserved')
        updated = data[:a] + data[b:]
    elif record['inserted']:
        b = stop + len(INSERT_SUFFIX)
        addition = INSERT_PREFIX + token + INSERT_SUFFIX
        a = key - 3  # newline and two tabs inserted immediately before the key
        if a < 0 or data[a:b] != addition or old:
            raise OptionsError('Inserted VDF text changed; preserved')
        updated = data[:a] + data[b:]
    else:
        updated = data[:start] + old + data[stop:]
    _, _, check = _locate(updated)
    if (record['inserted'] and check is not None) or (not record['inserted'] and (check is None or check[3] != _decode(old))):
        raise OptionsError('VDF restore round trip failed')
    _replace(path, data, info, updated)
