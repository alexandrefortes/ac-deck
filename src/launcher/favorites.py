"""Favoritos locais por ID; independentes do catálogo, da seleção e dos pins."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import uuid

from . import file_io as safe
from . import content


FILE_LIMIT = 4 * 1024 * 1024


def path_for(store):
    return Path(store).parent / 'favorites.json'


def clean(value=None):
    if value is None:
        return dict(schema_version=1, cars=[], tracks=[])
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'cars', 'tracks'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['cars'], list) or not isinstance(value['tracks'], list)):
        raise ValueError('Unsupported favorites file.')
    cars = sorted({content.identifier(car) for car in value['cars']})
    tracks = set()
    for row in value['tracks']:
        if not isinstance(row, dict) or set(row) != {'id', 'layout'}:
            raise ValueError('Invalid favorite track/layout.')
        tracks.add((content.identifier(row['id']), content.identifier(row['layout'], empty=True)))
    return dict(schema_version=1, cars=cars,
                tracks=[dict(id=identity, layout=layout) for identity, layout in sorted(tracks)])


def load(path):
    path = safe.absolute(path)
    safe.check_components(path)
    if not path.exists():
        return clean()
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size > FILE_LIMIT:
            raise ValueError('Favorites file is too large.')
        raw = stream.read(FILE_LIMIT + 1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    if (len(raw) > FILE_LIMIT or safe.signature(before) != safe.signature(after)
            or safe.signature(after) != safe.signature(current)):
        raise ValueError('Favorites changed while reading.')
    value = json.loads(raw.decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Invalid favorites file.')
    return clean(value)


def save(path, value):
    value = clean(value)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(raw) > FILE_LIMIT:
        raise ValueError('Favorites file is too large.')
    path = safe.absolute(path)
    safe.check_components(path)
    # Refuse to replace an invalid file, even if it changed after the UI loaded it.
    if path.exists():
        load(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.new')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
        safe.check_components(path)
        if path.exists():
            load(path)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return value


def contains(value, kind, row):
    if kind == 'cars':
        return row['id'] in value['cars']
    if kind == 'tracks':
        return dict(id=row['id'], layout=row.get('layout', '')) in value['tracks']
    return False


def recover(path):
    """Após confirmação explícita, preserva o original e inicia uma lista vazia."""
    path = safe.absolute(path)
    safe.check_components(path)
    stream, before = safe.open_reference(path)
    token = uuid.uuid4().hex
    backup = path.with_name('favorites-preserved-' + token + '.json')
    temporary = path.with_name(path.name + '.' + token + '.new')
    with stream, backup.open('xb') as output:
        shutil.copyfileobj(stream, output)
        after = os.fstat(stream.fileno())
    try:
        with temporary.open('xb') as output:
            output.write((json.dumps(clean(), indent=2) + '\n').encode('utf-8'))
        safe.check_components(path)
        current = path.lstat()
        safe.require_reference(current, path)
        if (safe.signature(before) != safe.signature(after)
                or safe.signature(after) != safe.signature(current)):
            raise ValueError('Favorites changed during recovery; original kept.')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return clean()


def toggle(value, kind, row):
    result = deepcopy(value)
    if kind == 'cars':
        item = content.identifier(row['id'])
    elif kind == 'tracks':
        item = dict(id=content.identifier(row['id']),
                    layout=content.identifier(row.get('layout', ''), empty=True))
    else:
        raise ValueError('Favorites support cars and track layouts only.')
    if item in result[kind]:
        result[kind].remove(item)
    else:
        result[kind].append(item)
    return clean(result)
