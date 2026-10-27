"""Fontes livres do pacote para o prefixo do jogo; cópias com recibo e reversão."""
from pathlib import Path
import os
import sys
import uuid

from . import file_io as safe

ALIASES = {'verdana.ttf': 'DejaVuSans.ttf', 'verdanai.ttf': 'DejaVuSans.ttf',
           'segoeui.ttf': 'DejaVuSans.ttf', 'segoeuil_0.ttf': 'DejaVuSans.ttf',
           'consola.ttf': 'DejaVuSansMono.ttf'}
LICENSE = 'DejaVu-LICENSE.txt'


def digest(path):
    return safe.hash_reference_file(Path(path))[0]


def bundle(destination, source, license_path):
    """Inclui fontes DejaVu existentes; não baixa nem instala componentes."""
    destination, source, license_path = Path(destination), Path(source), Path(license_path)
    safe.check_components(destination)
    if destination.exists():
        raise FileExistsError('Font bundle already exists')
    inputs = {name: source/name for name in sorted(set(ALIASES.values()))}
    inputs[LICENSE] = license_path
    rows = []
    for name, path in inputs.items():
        sha = digest(path)
        if name != LICENSE and path.read_bytes()[:4] not in (b'\0\1\0\0', b'OTTO', b'ttcf'):
            raise ValueError('Invalid font header: '+name)
        rows.append(dict(name=name, sha256=sha, size_bytes=path.stat().st_size))
    destination.mkdir(parents=True)
    for row in rows:
        safe.copy_verified(inputs[row['name']], destination/row['name'], row['sha256'])
    manifest = dict(schema_version=1, license='DejaVu', aliases=ALIASES, files=rows,
                    note='Aliases only; original bytes and internal font names preserved. '
                         'Italic/light aliases use regular Sans in this bundle.')
    safe.write_new_json(destination/'manifest.json', manifest)
    return manifest


def verify(payload):
    payload = safe.source_root(payload)
    manifest = safe.read_json(payload/'manifest.json')
    if manifest.get('schema_version') != 1 or manifest.get('aliases') != ALIASES:
        raise ValueError('Unknown font bundle')
    rows = manifest.get('files', [])
    if sorted(row['name'] for row in rows) != sorted(set(ALIASES.values()) | {LICENSE}):
        raise ValueError('Incomplete font bundle')
    for row in rows:
        path = payload/row['name']
        if digest(path) != row['sha256'] or path.stat().st_size != row['size_bytes']:
            raise ValueError('Font bundle changed: '+row['name'])
    return manifest


def font_directory(environment):
    value = environment.get('STEAM_COMPAT_DATA_PATH')
    if not value:
        raise ValueError('Steam/Proton prefix is missing')
    # Resolve somente o anchor recebido da Steam; descendentes não aceitam links.
    prefix = safe.source_root(Path(value).resolve(strict=True))
    windows = prefix/'pfx/drive_c/windows'
    safe.check_components(windows)
    if not windows.is_dir():
        raise ValueError('Existing Proton Windows directory is missing')
    candidates = [p for p in windows.iterdir() if p.name.casefold() == 'fonts']
    if len(candidates) > 1:
        raise ValueError('Ambiguous Proton Fonts directory')
    folder = candidates[0] if candidates else windows/'Fonts'
    safe.check_components(folder)
    if folder.exists() and not folder.is_dir():
        raise ValueError('Proton Fonts path is not a directory')
    return folder


def _save(path, value):
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    safe.write_new_json(temporary, value)
    temporary.replace(path)


def _read_receipt(path, folder):
    data = safe.read_json(path)
    names = set(ALIASES) | {LICENSE}
    sources = dict(ALIASES) | {LICENSE: LICENSE}
    if (data.get('schema_version') != 1 or data.get('fonts_root') != str(folder)
            or data.get('status') not in ('installing', 'ready', 'restored')
            or len(data.get('files', [])) != len(names)
            or {row['name'] for row in data['files']} != names
            or any(type(row.get('owned')) is not bool
                   or row.get('source') != sources[row['name']]
                   or not isinstance(row.get('existing_name'), str)
                   or row['existing_name'].casefold() != row['name'].casefold()
                   for row in data['files'])):
        raise ValueError('Font receipt does not match this prefix')
    return data


def install(payload, package, environment):
    """Acrescenta só aliases ausentes no prefixo atual, sem Registro/global."""
    payload, package = Path(payload), safe.source_root(package)
    manifest = verify(payload)
    folder = font_directory(environment)
    receipt = package/'launcher/csp-fonts.json'
    safe.check_components(receipt)
    if receipt.exists():
        previous = _read_receipt(receipt, folder)
        if previous['status'] != 'restored':
            if previous['bundle'] != manifest:
                raise ValueError('Restore previous font bundle before updating it')
            missing = []
            for row in previous['files']:
                path = folder/row['existing_name']
                safe.check_components(path)
                if not path.exists():
                    missing.append(row)
                elif row['owned'] and digest(path) != row['sha256']:
                    raise ValueError('Managed font changed; preserve it: '+row['name'])
            if previous['status'] != 'ready':
                raise ValueError('Interrupted font preparation; restore it before retrying')
            for row in missing:
                source = row['source']
                expected = digest(payload/source)
                path = folder/row['existing_name']
                temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
                safe.copy_verified(payload/source, temporary, expected)
                safe.check_components(path)
                if path.exists():
                    raise ValueError('Font destination appeared during repair; preserve it')
                temporary.replace(path)
                row.update(owned=True, sha256=expected)
            if missing:
                _save(receipt, previous)
            return previous
    sources = dict(ALIASES) | {LICENSE: LICENSE}
    rows = []
    # Conferir todos os destinos antes da primeira cópia. Fontes já presentes
    # permanecem externas e nunca se tornam propriedade deste pacote.
    for name, source in sources.items():
        candidates = ([p for p in folder.iterdir() if p.name.casefold() == name.casefold()]
                      if folder.exists() else [])
        if len(candidates) > 1:
            raise ValueError('Ambiguous existing font: '+name)
        path = candidates[0] if candidates else folder/name
        safe.check_components(path)
        existing = path.exists()
        if existing:
            safe.require_reference(path.lstat(), path)
        rows.append(dict(name=name, source=source, owned=not existing,
                         existing_name=path.name,
                         sha256=digest(path if existing else payload/source)))
    data = dict(schema_version=1, status='installing', fonts_root=str(folder),
                bundle=manifest, files=rows)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    _save(receipt, data)
    folder.mkdir(exist_ok=True)
    for row in rows:
        if row['owned']:
            safe.copy_verified(payload/row['source'], folder/row['name'], row['sha256'])
    data['status'] = 'ready'
    _save(receipt, data)
    return data


def _restore(package, environment):
    """Remove apenas cópias deste recibo, após conferir todas por hash."""
    package = safe.source_root(package)
    folder = font_directory(environment)
    receipt = package/'launcher/csp-fonts.json'
    data = _read_receipt(receipt, folder)
    if data['status'] == 'restored':
        return data
    owned = [row for row in data['files'] if row['owned'] and (folder/row['existing_name']).exists()]
    for row in owned:
        if digest(folder/row['existing_name']) != row['sha256']:
            raise ValueError('Managed font changed; nothing removed: '+row['name'])
    for row in owned:
        path = folder/row['existing_name']
        if digest(path) != row['sha256']:
            raise ValueError('Managed font changed during restoration: '+row['name'])
        path.unlink()
    data['status'] = 'restored'
    _save(receipt, data)
    return data


def restore(package, environment):
    """Usa a mesma trava do menu Linux antes de remover cópias do prefixo."""
    package = safe.source_root(package)
    lock = package/'launcher/active.lock'
    safe.check_components(lock)
    if sys.platform != 'linux' or not lock.exists():
        return _restore(package, environment)
    import fcntl
    with lock.open('r+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()), lock)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Close this launcher before restoring its fonts') from error
        return _restore(package, environment)
