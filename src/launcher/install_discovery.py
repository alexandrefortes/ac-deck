"""Read-only Steam library discovery for community installation.

Discovery identifies candidates; it does not authenticate ownership or start
Steam. A unique candidate can be selected automatically.
"""
from pathlib import Path
import os

from . import file_io as safe

APP_ID = '244210'
MAX_VDF_BYTES = 2 * 1024 * 1024


def _read_vdf(path):
    path = safe.absolute(path)
    stream, before = safe.open_regular(path)
    with stream:
        data = stream.read(MAX_VDF_BYTES + 1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    if (len(data) > MAX_VDF_BYTES or safe.signature(before) != safe.signature(after)
            or safe.signature(before) != safe.signature(path.lstat())):
        raise safe.SafetyError('Steam metadata is too large or changed while reading')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('Steam metadata is not UTF-8') from error
    return _parse_vdf(text)


def _parse_vdf(text):
    """Parse quoted KeyValues with bounded nesting and reject ambiguity."""
    pos, length = 0, len(text)
    opening, closing = object(), object()

    def token():
        nonlocal pos
        while pos < length:
            if text[pos].isspace():
                pos += 1
            elif text.startswith('//', pos):
                end = text.find('\n', pos + 2)
                pos = length if end < 0 else end + 1
            else:
                break
        if pos == length:
            return None
        if text[pos] in '{}':
            result = opening if text[pos] == '{' else closing
            pos += 1
            return result
        if text[pos] != '"':
            raise ValueError('Invalid Steam metadata token')
        pos += 1
        result = []
        while pos < length:
            char = text[pos]
            pos += 1
            if char == '"':
                return ''.join(result)
            if char == '\\':
                if pos >= length or text[pos] not in ('\\', '"'):
                    raise ValueError('Invalid Steam metadata escape')
                char = text[pos]
                pos += 1
            if char == '\x00':
                raise ValueError('Invalid Steam metadata character')
            result.append(char)
        raise ValueError('Unterminated Steam metadata string')

    def obj(depth, nested):
        if depth > 16:
            raise ValueError('Steam metadata nesting is too deep')
        values = {}
        while True:
            key = token()
            if key is None:
                if nested:
                    raise ValueError('Unclosed Steam metadata object')
                return values
            if key is closing:
                if not nested:
                    raise ValueError('Unexpected Steam metadata close')
                return values
            if key is opening or not key or key.casefold() in values:
                raise ValueError('Ambiguous Steam metadata key')
            value = token()
            if value is None or value is closing:
                raise ValueError('Missing Steam metadata value')
            values[key.casefold()] = obj(depth + 1, True) if value is opening else value

    return obj(0, False)


def validate_game(path):
    """Check an explicitly named directory without altering it."""
    game = safe.source_root(path)
    for name in ('acs.exe', 'AssettoCorsa.exe', 'cfg/video.ini', 'cfg/controls.ini',
                 'system/cfg/inireaderdocuments.ini'):
        reference = game / name
        safe.check_components(reference)
        try:
            safe.require_reference(reference.lstat(), reference)
        except FileNotFoundError as error:
            raise ValueError('The selected directory is not a complete Assetto Corsa installation') from error
    return game


def _library_candidate(library):
    manifest = library / 'steamapps' / ('appmanifest_' + APP_ID + '.acf')
    if not manifest.exists():
        return None
    app = _read_vdf(manifest).get('appstate')
    if not isinstance(app, dict) or app.get('appid') != APP_ID:
        raise ValueError('Steam app manifest does not identify Assetto Corsa')
    install = app.get('installdir')
    if not isinstance(install, str):
        raise ValueError('Steam app manifest has no installation directory')
    # Steam's install directory is one name, not a path from metadata.
    if '/' in install or '\\' in install:
        raise ValueError('Invalid Steam installation directory')
    safe.relative_file(install)
    return validate_game(library / 'steamapps' / 'common' / install)


def discover_from_root(root):
    """Read declared libraries for one root; results do not prove ownership."""
    root = safe.source_root(root)
    libraries = [root]
    folders = root / 'steamapps/libraryfolders.vdf'
    if folders.exists():
        parsed = _read_vdf(folders).get('libraryfolders')
        if not isinstance(parsed, dict):
            raise ValueError('Steam library metadata has no libraryfolders object')
        for key, value in parsed.items():
            if not key.isdecimal():
                continue
            name = value.get('path') if isinstance(value, dict) else value
            if not isinstance(name, str) or not Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Steam library metadata contains an invalid path')
            library = Path(name)
            if library.exists():
                libraries.append(safe.source_root(library.resolve(strict=True)))
    found, seen = [], set()
    for library in libraries:
        if library in seen:
            continue
        seen.add(library)
        game = _library_candidate(library)
        if game is not None and game not in found:
            found.append(game)
    return found


def discover(home=None):
    """Find declared game installations; default and Flatpak Steam roots only.

    Known Steam root aliases and library paths are resolved to their real
    directories for the read-only scan. Game descendants still obey file_io's
    no-link policy, as they will when attached.
    """
    home = safe.source_root(home if home is not None else Path.home())
    roots = (home / '.local/share/Steam', home / '.steam/steam',
             home / '.var/app/com.valvesoftware.Steam/.local/share/Steam')
    found, seen_roots = [], set()
    for root in roots:
        if not root.exists():
            continue
        root = safe.source_root(root.resolve(strict=True))
        if root in seen_roots:
            continue
        seen_roots.add(root)
        for game in discover_from_root(root):
            if game not in found:
                found.append(game)
    return found


def select_game(candidates, choice=None):
    """Require a selection from discovered paths or an explicit game path."""
    if choice is not None:
        return validate_game(choice)
    if len(candidates) != 1:
        raise ValueError('Select an Assetto Corsa installation explicitly')
    return validate_game(candidates[0])
