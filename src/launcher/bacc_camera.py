"""Câmeras pessoais BACC fixadas, com instalação e reparo sem executar Lua."""
from pathlib import Path
import hashlib
import stat
import uuid
import zipfile

from . import file_io as safe
from . import installed

SPECS = {
    'BACC - NFS Unbound': dict(version='1.0', slug='bacc-unbound',
        archive='BACC - NFS Unbound-1.0-20230126-135248.zip',
        sha256='2f87b49c7fbb65c05bca7d7d68e95bd1eab9443b493773374d38a75de269806c',
        members={'camera.lua': '87c85fb060d7b35b0def6899ff38c816917b434bb0f0351886dd6b5015473e6b',
                 'manifest.ini': '84c490f4ba0ef8f478181d1c6fded358daf02f2fc7cd4c652c3b87189f0e34a0'}),
    'BACC - GT': dict(version='1.2', slug='bacc-gt',
        archive='BACC - GT-1.2-20230110-185733.zip',
        sha256='bc10412dbbd5696565a7cacbcdb53b94cc6d3fa2c400cd947d72c4cf69ec4f4b',
        members={'camera.lua': '23db1a4a475b9770d946347e23a412afc2c68cfb5853036e2a7a1a99d5aefe4f',
                 'manifest.ini': '5297244f7bc4e97814fe89799f6173d5c32030ba91d8544d9a3abd675020da43'}),
}
PREFIX = b'''-- Old Man Assetto Corsa: private BACC adapter 1, original follows.
local baccSettings = ac.INIConfig.scriptSettings():mapSection('SETTINGS', {
  DISTANCE = 2.8, HEIGHT = 1.3, PITCH = 3.4
})
ac.getCameraParameters = function(index)
  return {distance = math.clamp(baccSettings.DISTANCE, 2.8, 8),
    height = math.clamp(baccSettings.HEIGHT, 0.5, 3),
    pitch = math.clamp(baccSettings.PITCH, -15, 15)}
end
'''
SUFFIX = b'''
-- Bind the author's callback without modifying its camera algorithm or FOV.
assert(type(update) == 'function', 'BACC update callback is missing')
script.update = update
'''
SETTINGS = b'[SETTINGS]\nDISTANCE=2.8\nHEIGHT=1.3\nPITCH=3.4\n'


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def source(archive, mode):
    if type(mode) is not str or mode not in SPECS:
        raise ValueError('Unknown BACC camera')
    spec = SPECS[mode]
    archive = safe.absolute(archive)
    sha, _ = safe.hash_reference_file(archive)
    if sha != spec['sha256']:
        raise ValueError('BACC archive differs from selected personal copy')
    root = 'extension/lua/chaser-camera/'+mode+'/'
    parts = root.rstrip('/').split('/')
    directories = {'/'.join(parts[:n])+'/' for n in range(1, len(parts)+1)}
    contents, seen = {}, set()
    stream, _ = safe.open_reference(archive)
    with stream, zipfile.ZipFile(stream) as zipped:
        for item in zipped.infolist():
            name = safe.relative_file(item.filename.rstrip('/'))
            if ('\\' in item.filename or name.casefold() in seen or item.flag_bits & 1
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Ambiguous, linked or encrypted BACC member')
            seen.add(name.casefold())
            if item.is_dir():
                if item.filename not in directories or item.file_size:
                    raise ValueError('Unexpected BACC directory')
                continue
            short = name.removeprefix(root)
            if name != root+short or short not in spec['members'] or item.file_size > 32*1024:
                raise ValueError('Unexpected BACC member')
            raw = zipped.read(item)
            if _hash(raw) != spec['members'][short]:
                raise ValueError('BACC member changed')
            contents[short] = raw
    if set(contents) != set(spec['members']) or safe.hash_reference_file(archive)[0] != sha:
        raise ValueError('Incomplete or changed BACC archive')
    return contents


def inspect(archive, mode):
    data = source(archive, mode)
    spec = SPECS[mode]
    return dict(implementation=mode, version=spec['version'], archive_sha256=spec['sha256'],
                authors='Aliex85; original credits retained', adapter_revision=1,
                public_redistribution_license='not supplied', personal_copy=True,
                software_executed=False, recommended=dict(distance=2.8, height=1.3, pitch=3.4),
                fov='Dynamic, controlled by original script',
                files=[dict(path=name, sha256=_hash(raw)) for name, raw in data.items()])


def assets(archive, mode):
    original = source(archive, mode)
    data = {'camera-original.lua': original['camera.lua'],
            'camera.lua': PREFIX+original['camera.lua']+SUFFIX,
            'manifest.ini': original['manifest.ini'], 'settings.ini': SETTINGS}
    return [dict(path=name, data=raw, sha256=_hash(raw)) for name, raw in sorted(data.items())]


def install(archive, package, mode):
    """Chamador mantém active.lock. Conserva originais e bloqueia modificados."""
    rows = assets(archive, mode)
    spec = SPECS[mode]
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder = game/'extension/lua/chaser-camera'/mode
    receipt = package/'launcher'/(spec['slug']+'.json')
    for path in (folder, receipt):
        safe.check_components(path)
    expected = dict(schema_version=1, implementation=mode, folder=str(folder),
                    archive_sha256=spec['sha256'], adapter_revision=1,
                    files=[dict(path=r['path'], sha256=r['sha256']) for r in rows])
    if receipt.exists():
        record = safe.read_json(receipt)
        internal = package/'game'
        moved = (folder.is_relative_to(internal) and isinstance(record.get('folder'), str)
                 and record['folder'].endswith('/game/'+folder.relative_to(internal).as_posix()))
        if (any(record.get(k) != v for k, v in expected.items() if k != 'folder')
                or (record.get('folder') != str(folder) and not moved)
                or record.get('status') not in ('installing', 'ready')):
            raise ValueError('BACC receipt differs; preserve existing files')
    else:
        if folder.parent.exists() and any(p.name.casefold() == mode.casefold() for p in folder.parent.iterdir()):
            raise ValueError('Unknown existing BACC camera; preserve it')
        record = dict(expected, status='installing')
    missing = []
    for row in rows:
        target = folder/row['path']
        safe.check_components(target)
        if target.exists():
            if safe.hash_reference_file(target)[0] != row['sha256']:
                raise ValueError('Managed BACC camera changed; preserve it')
        else:
            missing.append(row)
    relocated = record['folder'] != str(folder)
    if record['status'] == 'ready' and not missing and not relocated:
        return record
    record['folder'] = str(folder)
    def save(status):
        record['status'] = status
        safe.check_components(receipt)
        if receipt.exists():
            safe.require_reference(receipt.lstat(), receipt)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt.with_name(spec['slug']+'-'+uuid.uuid4().hex+'.json')
        safe.write_new_json(temporary, record)
        temporary.replace(receipt)
    save('installing')
    for row in missing:
        target = folder/row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.new')
        safe.check_components(temporary)
        with temporary.open('xb') as stream:
            stream.write(row['data'])
        if safe.hash_reference_file(temporary)[0] != row['sha256']:
            raise ValueError('BACC temporary copy changed')
        safe.check_components(target)
        if target.exists():
            raise ValueError('BACC destination appeared; preserve it')
        temporary.replace(target)
    save('ready')
    return record
