"""Estado atômico, ambiente de subprocessos e travas liberadas pelo SO."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile


class CycleError(RuntimeError):
    pass


def read_json(path):
    check_path(path)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path)
    check_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.new', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def relative(value):
    if not isinstance(value, str):
        raise CycleError('Path relativo deve ser texto')
    p = PurePosixPath(value)
    if (not isinstance(value, str) or not value or p.is_absolute() or '\\' in value
            or ':' in value or '\x00' in value or str(p) != value
            or any(part.casefold() in ('.', '..', '.git') for part in p.parts)):
        raise CycleError('Path relativo não canônico: '+str(value))
    return value


def file_state(path):
    path = Path(path)
    check_path(path)
    if path.is_symlink():
        raise CycleError('Link não permitido: '+str(path))
    if not path.exists():
        return None
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise CycleError('Arquivo regular necessário: '+str(path))
    from src.launcher.file_io import hash_reference_file
    sha, info = hash_reference_file(path)
    return dict(sha256=sha, size=info.st_size,
                mode=stat.S_IMODE(info.st_mode) if os.name != 'nt' else None)


def check_path(path):
    from src.launcher.file_io import check_components
    check_components(Path(path).absolute())


def sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def process_env(extra=None):
    # Só o filho: não remover proxies, CA, HOME, autenticação ou opções explícitas.
    removed = {'LD_PRELOAD', 'SteamGameId', 'SteamAppId', 'SteamOverlayGameId',
               'STEAM_COMPAT_APP_ID', 'STEAM_COMPAT_DATA_PATH',
               'STEAM_COMPAT_CLIENT_INSTALL_PATH', 'PYTHONHOME', 'PYTHONPATH'}
    env = {k: v for k, v in os.environ.items() if k not in removed}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if extra:
        env.update(extra)
    return env


@contextmanager
def locked(path):
    """A existência do arquivo não é a trava. Nunca inferir abandono por PID/idade."""
    path = Path(path)
    check_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        from src.launcher.file_io import require_reference
        require_reference(path.lstat(), path)
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise CycleError('Operação já em execução: '+str(path)) from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
