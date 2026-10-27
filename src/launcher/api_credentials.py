"""Chave própria local. Nunca faz parte da seleção, proposta ou entrega Git."""
import os
from pathlib import Path
import re
import uuid
from . import file_io as safe

KEY = re.compile(r'sk-[A-Za-z0-9_-]{16,500}\Z')


def validate(value):
    value = value.strip() if isinstance(value, str) else ''
    if not KEY.fullmatch(value):
        raise ValueError('Paste a valid OpenAI API key. The key is never sent through Git.')
    return value


def path_for(store):
    return Path(store).parent/'private/openai-api-key'


def load(path):
    path = safe.absolute(path)
    safe.check_components(path)
    if not path.exists():
        return ''
    safe.require_reference(path.lstat(), path)
    if path.stat().st_size > 512 or (os.name == 'posix' and path.stat().st_mode & 0o077):
        raise ValueError('Local API key permissions are unsafe. Remove it and paste it again.')
    stream, _ = safe.open_reference(path)
    with stream:
        return validate(stream.read(513).decode('ascii'))


def forget(path):
    path = safe.absolute(path)
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
        path.unlink()


def save(path, value):
    value = validate(value)
    path = safe.absolute(path)
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name('openai-'+uuid.uuid4().hex+'.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            stream.write(value)
        safe.check_components(path)
        if path.exists():
            safe.require_reference(path.lstat(), path)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
