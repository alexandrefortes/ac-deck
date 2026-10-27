"""Estilo de compatibilidade: mesmo HLSL, sem o include externo do gamma.

Cria uma cópia independente do estilo base. Não altera a distribuição CSP.
O efeito real requer teste no Deck; isto não corrige o carregador do Wine.
"""
import hashlib
import os
from pathlib import Path
import sys
import uuid

from . import file_io as safe
from . import csp, installed

STYLE = 'old_man_linear_inline'
GAMMA_SHA256 = 'b55c9304167a5d02ed1f7a29065cd6a27fa7b33bb27962160105d96501bef8da'
CONSUMERS = ('src/render_linear.lua', 'src/render_postprocessing.lua')


def plan(payload):
    payload = Path(payload)
    manifest = csp.verify(payload)
    prefix = 'extension/weather/base/'
    selected = [r for r in manifest['files'] if r['path'].startswith(prefix)]
    shader = payload/(prefix+'shaders/pp_gamma.fx')
    raw = shader.read_bytes()
    if hashlib.sha256(raw).hexdigest() != GAMMA_SHA256 or b']=]' in raw:
        raise ValueError('Unexpected gamma shader; preserve this CSP version')
    rows = []
    for row in selected:
        relative = row['path'][len(prefix):]
        data = (payload/row['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Base style changed during preparation: '+relative)
        if relative in CONSUMERS:
            token = b"shader = 'shaders/pp_gamma.fx'"
            if data.count(token) != 1:
                raise ValueError('Unexpected gamma consumer: '+relative)
            data = data.replace(token, b'shader = [=['+raw+b']=]')
        elif relative == 'manifest.ini':
            token = b'NAME = Default'
            if data.count(token) != 1:
                raise ValueError('Unexpected base style manifest')
            data = data.replace(token, b'NAME = Old Man - inline gamma test')
        rows.append(dict(path=relative, data=data, sha256=hashlib.sha256(data).hexdigest()))
    names = {r['path'] for r in rows}
    if not {*CONSUMERS, 'manifest.ini', 'weather.lua', 'settings.ini'} <= names:
        raise ValueError('Incomplete base weather style')
    return rows


def _context(package):
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder = game/'extension/weather'/STYLE
    receipt = package/'launcher/linear-gamma.json'
    safe.check_components(folder)
    safe.check_components(receipt)
    return folder, receipt


def _save(receipt, data):
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_name('linear-gamma-'+uuid.uuid4().hex+'.json')
    safe.write_new_json(temporary, data)
    temporary.replace(receipt)


def _expected(folder, rows):
    return dict(schema_version=1, style=STYLE, folder=str(folder),
                gamma_sha256=GAMMA_SHA256,
                files=[dict(path=r['path'], sha256=r['sha256']) for r in rows])


def _read(receipt, expected):
    data = safe.read_json(receipt)
    if any(data.get(k) != v for k, v in expected.items()):
        raise ValueError('Inline gamma receipt does not match this package/style')
    if data.get('status') not in ('installing', 'ready', 'restored'):
        raise ValueError('Invalid inline gamma receipt status')
    return data


def install(payload, package):
    rows = plan(payload)
    folder, receipt = _context(package)
    expected = _expected(folder, rows)
    if receipt.exists():
        previous = _read(receipt, expected)
        if previous['status'] == 'ready':
            for row in rows:
                if csp.digest(folder/row['path']) != row['sha256']:
                    raise ValueError('Managed inline gamma style changed: '+row['path'])
            return previous
        if previous['status'] != 'restored':
            raise ValueError('Interrupted inline gamma preparation; restore before retrying')
    # Nenhum diretório preexistente passa a ser propriedade deste pacote.
    if folder.exists():
        raise ValueError('Inline gamma style already exists; preserve it')
    data = dict(expected, status='installing')
    _save(receipt, data)
    folder.mkdir()
    for row in rows:
        target = folder/row['path']
        safe.check_components(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(row['data'])
        if csp.digest(target) != row['sha256']:
            raise ValueError('Inline gamma copy changed: '+row['path'])
    data['status'] = 'ready'
    _save(receipt, data)
    return data


def _restore(payload, package):
    """Jogo/menu fechados. Confere tudo antes de remover só arquivos próprios."""
    rows = plan(payload)
    folder, receipt = _context(package)
    data = _read(receipt, _expected(folder, rows))
    if data['status'] == 'restored':
        return data
    present = []
    for row in rows:
        path = folder/row['path']
        safe.check_components(path)
        if path.exists():
            if csp.digest(path) != row['sha256']:
                raise ValueError('Managed inline gamma style changed; nothing removed: '+row['path'])
            present.append(path)
    # Arquivos acrescentados por terceiros ficam preservados. Retirar apenas
    # pastas vazias ascendentes das cópias conhecidas, sem exclusão recursiva.
    for path in present:
        expected = next(r['sha256'] for r in rows if folder/r['path'] == path)
        if csp.digest(path) != expected:
            raise ValueError('Inline gamma style changed during restoration')
        path.unlink()
    parents = {p for path in present for p in path.parents if p.is_relative_to(folder)}
    for path in sorted(parents, key=lambda p:len(p.parts), reverse=True):
        if path.exists() and not any(path.iterdir()):
            path.rmdir()
    if folder.exists() and not any(folder.iterdir()):
        folder.rmdir()
    data['status'] = 'restored'
    _save(receipt, data)
    return data


def restore(payload, package):
    package = safe.source_root(package)
    lock = package/'launcher/active.lock'
    safe.check_components(lock)
    if sys.platform != 'linux' or not lock.exists():
        return _restore(payload, package)
    import fcntl
    with lock.open('r+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()), lock)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Close this launcher before restoring its gamma style') from error
        return _restore(payload, package)
