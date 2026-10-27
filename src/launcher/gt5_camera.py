"""Câmera GT5 pessoal incluída na entrega privada, com cópia e reparo por hash.

O ZIP original não possui licença de redistribuição pública. Não baixar outra
versão nem tratar a incorporação privada como liberação pública do mod.
"""
from pathlib import Path
import hashlib
import os
import stat
import sys
import uuid
import zipfile

from . import file_io as safe

IMPLEMENTATION = 'spec 2.0'
ARCHIVE_NAME = 'granturismo5cam.zip'
ARCHIVE_SHA256 = 'c8698f10a9090caef5d455a72240edbd5239f0a199b77269527ca1b5c5dcca5d'
SOURCE_URL = 'https://www.overtake.gg/downloads/spec-2-0-gran-turismo-5-gt5-chase-camera.68401/'
ARCHIVE_ROOT = 'assettocorsa/extension/lua/chaser-camera/spec 2.0/'
SOURCE_HASHES = {
    'camera.lua': '819f3b8bb56f063a13b0326a06495ea978aedb0b64d8a4dc4d9f4e84de63d8d2',
    'manifest.ini': '967e776973baa7f17c5fdbcc63e19368aec65e64abbb0cc9835c7d3ef6bcf543',
}
ADAPTER_REVISION = 1
# O mod usa o getter nativo. A adaptação limita a substituição ao ambiente Lua
# desta câmera; não escreve system/cfg/chase_cam.ini nem altera outras vistas.
PREFIX = b'''-- Old Man Assetto Corsa: private Spec 2.0 integration, adapter 1.
local gt5Settings = ac.INIConfig.scriptSettings():mapSection('SETTINGS', {
  DISTANCE = 5.7, HEIGHT = 1.6, PITCH = 0
})
ac.getCameraParameters = function(index)
  return {distance = math.clamp(gt5Settings.DISTANCE, 3, 8),
    height = math.clamp(gt5Settings.HEIGHT, 0.5, 3),
    pitch = math.clamp(gt5Settings.PITCH, -15, 15)}
end
'''
SUFFIX = b'''
-- CSP 0.2.11 callback; original update(dt, cameraIndex) is preserved above.
assert(type(update) == 'function', 'Spec 2.0 update callback is missing')
script.update = update
'''
SETTINGS = b'[SETTINGS]\nDISTANCE=5.7\nHEIGHT=1.6\nPITCH=0\n'


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _source(archive):
    archive = safe.absolute(archive)
    digest, before = safe.hash_reference_file(archive)
    if digest != ARCHIVE_SHA256:
        raise ValueError('GT5 camera ZIP differs from the selected archive')
    stream, _ = safe.open_reference(archive)
    contents = {}
    directories = {'/'.join(ARCHIVE_ROOT.rstrip('/').split('/')[:index])
                   for index in range(1, len(ARCHIVE_ROOT.rstrip('/').split('/'))+1)}
    seen = set()
    with stream, zipfile.ZipFile(stream) as source:
        for item in source.infolist():
            name = safe.relative_file(item.filename.rstrip('/'))
            if (name.casefold() in seen or '\\' in item.filename
                    or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Duplicate, linked or encrypted GT5 ZIP member')
            seen.add(name.casefold())
            if item.is_dir():
                if name not in directories or item.filename != name+'/' or item.file_size:
                    raise ValueError('Unexpected GT5 camera ZIP directory')
                continue
            short = name.removeprefix(ARCHIVE_ROOT)
            if (name != ARCHIVE_ROOT+short or short not in SOURCE_HASHES
                    or short in contents or item.is_dir() or item.flag_bits & 1
                    or stat.S_ISLNK(item.external_attr >> 16)
                    or item.file_size > 16*1024):
                raise ValueError('Unexpected GT5 camera ZIP member')
            raw = source.read(item)
            if _hash(raw) != SOURCE_HASHES[short]:
                raise ValueError('GT5 camera member changed: '+short)
            contents[short] = raw
    if set(contents) != set(SOURCE_HASHES):
        raise ValueError('Incomplete GT5 camera ZIP')
    if safe.hash_reference_file(archive)[0] != digest:
        raise ValueError('GT5 camera ZIP changed while reading')
    return contents, before.st_size


def inspect(archive):
    contents, size = _source(archive)
    return dict(schema_version=1, implementation=IMPLEMENTATION, version='1.0',
                archive_sha256=ARCHIVE_SHA256, archive_size_bytes=size,
                source_url=SOURCE_URL, authors='kirbyguy22/rapidough1',
                public_redistribution_license='not supplied', adapter_revision=ADAPTER_REVISION,
                files=[dict(path=name, sha256=_hash(raw), size_bytes=len(raw))
                       for name, raw in contents.items()], software_executed=False)


def assets(archive):
    contents, _ = _source(archive)
    data = {'camera-original.lua': contents['camera.lua'],
            'camera.lua': PREFIX+contents['camera.lua']+SUFFIX,
            'manifest.ini': contents['manifest.ini'], 'settings.ini': SETTINGS}
    return [dict(path=name, data=raw, sha256=_hash(raw)) for name, raw in data.items()]


def _context(package):
    from . import installed
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder = game/'extension/lua/chaser-camera'/IMPLEMENTATION
    receipt = package/'launcher/gt5-camera.json'
    safe.check_components(folder)
    safe.check_components(receipt)
    return folder, receipt


def _expected(folder, rows):
    return dict(schema_version=1, implementation=IMPLEMENTATION, folder=str(folder),
                archive_sha256=ARCHIVE_SHA256, adapter_revision=ADAPTER_REVISION,
                files=[{key: row[key] for key in ('path', 'sha256')} for row in rows])


def _read(receipt, expected):
    data = safe.read_json(receipt)
    folder = Path(expected['folder'])
    internal = receipt.parent.parent/'game'
    moved = (folder.is_relative_to(internal) and isinstance(data.get('folder'), str)
             and data['folder'].endswith('/game/'+folder.relative_to(internal).as_posix()))
    if (any(data.get(key) != value for key, value in expected.items() if key != 'folder')
            or (data.get('folder') != str(folder) and not moved)
            or data.get('status') not in ('installing', 'ready', 'restored')):
        raise ValueError('GT5 camera receipt differs; preserve existing files')
    return data


def _save(receipt, data):
    safe.check_components(receipt)
    if receipt.exists():
        safe.require_reference(receipt.lstat(), receipt)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_name('gt5-camera-'+uuid.uuid4().hex+'.json')
    safe.write_new_json(temporary, data)
    temporary.replace(receipt)


def _present(folder, rows):
    missing = []
    for row in rows:
        path = folder/row['path']
        safe.check_components(path)
        if path.exists():
            if safe.hash_reference_file(path)[0] != row['sha256']:
                raise ValueError('Managed GT5 camera changed; preserve it: '+row['path'])
        else:
            missing.append(row)
    return missing


def install(archive, package):
    """Chamador mantém a trava do launcher. Não executa Lua ou o simulador."""
    rows = assets(archive)
    folder, receipt = _context(package)
    expected = _expected(folder, rows)
    if receipt.exists():
        data = _read(receipt, expected)
    else:
        if folder.exists():
            raise ValueError('Unknown existing GT5 camera directory; preserve it')
        data = dict(expected, status='installing')
    # Conferir todos os arquivos presentes antes da primeira escrita/reparação.
    missing = _present(folder, rows)
    if data['status'] == 'ready' and not missing:
        if data['folder'] != str(folder):
            data['folder'] = str(folder)
            _save(receipt, data)
        return data
    data['folder'] = str(folder)
    _save(receipt, dict(data, status='installing'))
    folder.mkdir(parents=True, exist_ok=True)
    for row in missing:
        path = folder/row['path']
        temporary = folder/(row['path']+'.'+uuid.uuid4().hex+'.new')
        safe.check_components(temporary)
        with temporary.open('xb') as stream:
            stream.write(row['data'])
        if safe.hash_reference_file(temporary)[0] != row['sha256']:
            raise ValueError('GT5 camera temporary copy changed')
        safe.check_components(path)
        if path.exists():
            raise ValueError('GT5 camera destination appeared during copy; preserve it')
        temporary.replace(path)
    _present(folder, rows)
    data['status'] = 'ready'
    _save(receipt, data)
    return data


def _restore(archive, package):
    rows = assets(archive)
    folder, receipt = _context(package)
    data = _read(receipt, _expected(folder, rows))
    if data['status'] == 'restored':
        return data
    _present(folder, rows)
    for row in rows:
        path = folder/row['path']
        if path.exists():
            if safe.hash_reference_file(path)[0] != row['sha256']:
                raise ValueError('GT5 camera changed during restoration')
            path.unlink()
    if folder.exists() and not any(folder.iterdir()):
        folder.rmdir()
    data.update(status='restored', folder=str(folder))
    _save(receipt, data)
    return data


def restore(archive, package):
    package = safe.source_root(package)
    lock = package/'launcher/active.lock'
    safe.check_components(lock)
    if sys.platform != 'linux' or not lock.exists():
        return _restore(archive, package)
    import fcntl
    with lock.open('r+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()), lock)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Close the launcher before restoring the GT5 camera') from error
        return _restore(archive, package)
