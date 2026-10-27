"""Preferências privadas e revisões, sem rede ou mudanças na corrida."""
import hashlib
import json
import os
from pathlib import Path
import uuid

from . import file_io as safe

TEXT_LIMIT = 8*1024
FILE_LIMIT = TEXT_LIMIT*6+4*1024


def path_for(store):
    return Path(store).parent/'private/ai-preferences.json'


def clean(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or value.get('schema_version', 1) != 1:
        raise ValueError('Unsupported AI preferences file.')
    text = value.get('text', '')
    if not isinstance(text, str):
        raise ValueError('Custom prompt must be text.')
    if len(text.encode('utf-8')) > TEXT_LIMIT:
        raise ValueError('Custom prompt exceeds 8 KiB. Shorten it before saving; text was kept.')
    for key in ('voice_enabled', 'use_generation_key'):
        if type(value.get(key, False)) is not bool:
            raise ValueError('Invalid dictation settings.')
    device = value.get('voice_device', '')
    if (not isinstance(device, str) or len(device.encode('utf-8')) > 1024
            or any(ord(char) < 32 for char in device)):
        raise ValueError('Invalid microphone selection.')
    return dict(schema_version=1, text=text if text.strip() else '',
                voice_enabled=value.get('voice_enabled', False),
                use_generation_key=value.get('use_generation_key', False),
                voice_device=device)


def revision(value):
    return hashlib.sha256(clean(value)['text'].encode('utf-8')).hexdigest()


def load(path):
    path = safe.absolute(path)
    safe.check_components(path)
    if not path.exists():
        return clean()
    safe.require_reference(path.lstat(), path)
    if path.stat().st_size > FILE_LIMIT or (os.name == 'posix' and path.stat().st_mode & 0o077):
        raise ValueError('AI preferences file size or permissions are unsafe.')
    stream, before = safe.open_reference(path)
    with stream:
        raw = stream.read(FILE_LIMIT+1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    if (len(raw) > FILE_LIMIT or safe.signature(before) != safe.signature(after)
            or safe.signature(after) != safe.signature(path.lstat())):
        raise ValueError('AI preferences changed while reading.')
    return clean(json.loads(raw.decode('utf-8')))


def save(path, value):
    value = clean(value)
    path = safe.absolute(path)
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name('ai-preferences-'+uuid.uuid4().hex+'.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
        safe.check_components(path)
        if path.exists():
            safe.require_reference(path.lstat(), path)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return value
