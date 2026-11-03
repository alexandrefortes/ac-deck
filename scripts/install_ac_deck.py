#!/usr/bin/env python3
"""Install an explicitly identified ac-deck archive without overwriting data.

No release URL or checksum is assumed. Obtain both from the release publisher.
This standalone script uses only Python's standard library.
"""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import select
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import urllib.parse
import urllib.request


ARCHIVE_LIMIT = 2 * 1024 * 1024 * 1024
EXTRACT_LIMIT = 4 * 1024 * 1024 * 1024
ENTRY_LIMIT = 50000
ROOT_NAME = 'ac-deck-linux-x86_64'
TERMS = (
    'ac-deck is provided as-is, without warranties or conditions. To the extent '
    'permitted by law, the creator is not liable for damages arising from this software.\n\n'
    'Personal, noncommercial modifications are allowed under the PolyForm '
    'Noncommercial License 1.0.0:\n'
    'https://polyformproject.org/licenses/noncommercial/1.0.0\n\n'
    'Other grants, legal rights and dependency licenses still apply.'
)
_TERMS_ENTER = '\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1006h'
_TERMS_LEAVE = '\x1b[?1006l\x1b[?1000l\x1b[0m\x1b[?25h\x1b[?1049l'


class InstallError(RuntimeError):
    pass


def _terms_screen(size, selected):
    width = min(size.columns, 80)
    lines = ['ac-deck installation', '']
    for paragraph in TERMS.split('\n\n'):
        for line in paragraph.splitlines():
            lines.extend(textwrap.wrap(line, width=max(width, 1)))
        lines.append('')
    lines.extend(textwrap.wrap('Do you agree to these terms and want to install ac-deck?', width=max(width, 1)))
    lines.extend(textwrap.wrap('Arrows/Tab: select. Enter: confirm. Y/N or click. Esc: cancel.', width=max(width, 1)))
    lines.append('')
    row = len(lines) + 1
    if width < 20 or row > size.lines:
        raise InstallError('Enlarge the terminal to display the installation terms')
    buttons = ('\x1b[7m[ Yes ]\x1b[0m    [ No ]' if selected
               else '[ Yes ]    \x1b[7m[ No ]\x1b[0m')
    return '\x1b[2J\x1b[H' + '\r\n'.join(lines) + '\r\n' + buttons, row


def _terms_event(key, selected, button_row):
    if key in (b'', b'\x04'):
        raise EOFError
    if key == b'\x03':
        raise KeyboardInterrupt
    if key in (b'y', b'Y', b'n', b'N', b'\x1b', b'\r', b'\n'):
        return selected, (key in (b'y', b'Y') or (key in (b'\r', b'\n') and selected))
    if key in (b'\x1b[A', b'\x1b[D', b'\x1bOA', b'\x1bOD'):
        selected = True
    elif key in (b'\x1b[B', b'\x1b[C', b'\x1bOB', b'\x1bOC'):
        selected = False
    elif key == b'\t':
        selected = not selected
    else:
        click = re.fullmatch(rb'\x1b\[<0;(\d+);(\d+)M', key)
        if click and int(click[2]) == button_row:
            column = int(click[1])
            if 1 <= column <= 7:
                return selected, True
            if 12 <= column <= 17:
                return selected, False
    return selected, None


def _read_terms_key(fd):
    key = os.read(fd, 1)
    if key != b'\x1b':
        return key
    while len(key) < 32 and select.select([fd], [], [], 0.2)[0]:
        part = os.read(fd, 1)
        if not part:
            raise EOFError
        key += part
        if ((len(key) == 2 and part not in (b'[', b'O'))
                or (len(key) >= 3 and 0x40 <= part[0] <= 0x7e)):
            break
    return key


def _confirm_terms():
    """Read the controlling terminal, including when stdin carries piped code."""
    try:
        import termios
    except ImportError as error:
        raise InstallError('Interactive terms require a Linux terminal; automation needs --accept-terms') from error
    try:
        fd = os.open('/dev/tty', os.O_RDWR | getattr(os, 'O_NOCTTY', 0))
    except OSError as error:
        raise InstallError('Terms need a terminal; automation needs explicit --accept-terms') from error
    previous, changed, screen = None, False, False
    try:
        if not os.isatty(fd):
            raise InstallError('Terms need an interactive terminal')
        size, selected = os.get_terminal_size(fd), False
        rendered, row = _terms_screen(size, selected)
        previous = termios.tcgetattr(fd)
        mode = previous[:]
        mode[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN)
        mode[6] = previous[6][:]
        mode[6][termios.VMIN], mode[6][termios.VTIME] = 1, 0
        termios.tcsetattr(fd, termios.TCSAFLUSH, mode)
        changed, screen = True, True
        os.write(fd, (_TERMS_ENTER + rendered).encode())
        while True:
            key = _read_terms_key(fd)
            current = os.get_terminal_size(fd)
            if current != size:
                size = current
            else:
                selected, answer = _terms_event(key, selected, row)
                if answer is not None:
                    return answer
            rendered, row = _terms_screen(size, selected)
            os.write(fd, rendered.encode())
    finally:
        try:
            try:
                if screen:
                    os.write(fd, _TERMS_LEAVE.encode())
            finally:
                if changed:
                    termios.tcsetattr(fd, termios.TCSANOW, previous)
        finally:
            os.close(fd)


def _absolute(path):
    path = Path(path).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise InstallError('Use an absolute path without traversal')
    return path


def _check_components(path):
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise InstallError('Symbolic links and reparse points are not accepted: ' + str(current))


def _mkdir_parents(path):
    _check_components(path)
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise InstallError('Installation parent is not a directory')
    for directory in reversed(missing):
        directory.mkdir()
        _check_components(directory)


def _default_destination():
    base = os.environ.get('XDG_DATA_HOME')
    return (_absolute(base) if base else _absolute(Path.home() / '.local/share')) / 'ac-deck'


def _https_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise InstallError('Download URL must be HTTPS and must not contain credentials')


class _HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _copy_hash(source, target):
    digest, total = hashlib.sha256(), 0
    with target.open('xb') as out:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > ARCHIVE_LIMIT:
                raise InstallError('Archive exceeds the size limit')
            digest.update(block)
            out.write(block)
    return digest.hexdigest()


def _stage_archive(archive, url, target, expected):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
        raise InstallError('SHA-256 must contain 64 hexadecimal digits')
    if url is not None:
        _https_url(url)
        opener = urllib.request.build_opener(_HttpsRedirect())
        with opener.open(url, timeout=60) as source:
            _https_url(source.geturl())
            actual = _copy_hash(source, target)
    else:
        archive = _absolute(archive)
        _check_components(archive)
        info = archive.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise InstallError('Archive must be an independent regular file')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        with os.fdopen(os.open(archive, flags), 'rb') as source:
            before = os.fstat(source.fileno())
            actual = _copy_hash(source, target)
            after = os.fstat(source.fileno())
        _check_components(archive)
        current = archive.lstat()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
        if identity(info) != identity(before) or identity(before) != identity(after) or identity(after) != identity(current):
            raise InstallError('Archive changed while being read')
    if actual != expected.lower():
        raise InstallError('Archive SHA-256 does not match the supplied checksum')


def _extract_archive(archive, stage):
    entries, seen, total = [], set(), 0
    with tarfile.open(archive, mode='r:gz') as tar:
        for member in tar:
            if len(entries) >= ENTRY_LIMIT:
                raise InstallError('Archive contains too many entries')
            name = member.name
            parts = PurePosixPath(name).parts
            if (not name or name.startswith('/') or '\\' in name or '\x00' in name
                    or any(part in ('', '.', '..') for part in name.split('/'))
                    or not parts or parts[0] != ROOT_NAME or name.casefold() in seen):
                raise InstallError('Archive contains an unsafe or duplicate path')
            if not (member.isdir() or member.isfile()):
                raise InstallError('Archive contains a link or special file')
            if member.size < 0:
                raise InstallError('Archive contains a negative size')
            total += member.size
            if total > EXTRACT_LIMIT:
                raise InstallError('Archive contents exceed the size limit')
            seen.add(name.casefold())
            entries.append(member)
        if ROOT_NAME + '/ac-deck' not in {m.name for m in entries if m.isfile()}:
            raise InstallError('Archive does not contain the ac-deck executable')
        for member in entries:
            target = stage.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)


def _publish(stage, destination):
    """Create a new destination and files exclusively; never replace a path."""
    _check_components(destination)
    destination.mkdir()
    try:
        for directory, subdirs, files in os.walk(stage, followlinks=False):
            relative = Path(directory).relative_to(stage)
            output_dir = destination / relative
            for name in subdirs:
                target = output_dir / name
                _check_components(target)
                target.mkdir()
            for name in files:
                source, target = Path(directory) / name, output_dir / name
                _check_components(target)
                with source.open('rb') as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                    if hasattr(os, 'fchmod'):
                        os.fchmod(dst.fileno(), source.stat().st_mode & 0o777)
                    else:
                        target.chmod(source.stat().st_mode & 0o777)
    except (OSError, InstallError) as error:
        raise InstallError('Installation is incomplete; partial directory was preserved: ' + str(destination)) from error


def _file_fingerprint(path):
    """Hash an independent regular file and reject changes while reading it."""
    _check_components(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise InstallError('Installed file is not an independent regular file: ' + str(path))
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    digest = hashlib.sha256()
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        while block := stream.read(1024 * 1024):
            digest.update(block)
        after = os.fstat(stream.fileno())
    _check_components(path)
    current = path.lstat()
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                             info.st_mode, info.st_nlink)
    if not (identity(before) == identity(opened) == identity(after) == identity(current)):
        raise InstallError('Installed file changed during verification: ' + str(path))
    return (before.st_size, digest.hexdigest(), stat.S_IMODE(before.st_mode))


def _inventory(root):
    _check_components(root)
    if not root.is_dir():
        raise InstallError('Installation directory is missing')
    directories, files = set(), {}
    def onerror(error):
        raise error
    for directory, subdirs, names in os.walk(root, followlinks=False, onerror=onerror):
        relative = Path(directory).relative_to(root)
        for name in subdirs:
            path = Path(directory) / name
            _check_components(path)
            if not path.is_dir():
                raise InstallError('Unexpected installation directory: ' + str(path))
            directories.add((relative / name).as_posix())
        for name in names:
            path = Path(directory) / name
            files[(relative / name).as_posix()] = _file_fingerprint(path)
    return directories, files


def _run_setup(destination):
    command = [str(destination / 'ac-deck'), 'install']
    if sys.stdin.isatty():
        subprocess.run(command, check=True)
    else:
        try:
            tty = open('/dev/tty', 'r+', encoding='utf-8')
        except OSError as error:
            raise InstallError('Setup needs a terminal; rerun the installed command in a terminal') from error
        with tty:
            subprocess.run(command, stdin=tty, stdout=tty, stderr=tty, check=True)


def _verify_existing(destination, expected):
    """Reuse only an exact payload; leave additional player files untouched."""
    _check_components(destination)
    if not destination.is_dir():
        raise InstallError('Installation destination is not a directory')
    directories, files = expected
    for name in sorted(directories):
        path = destination / name
        _check_components(path)
        if not path.is_dir():
            raise InstallError('Existing installation is incomplete; files were preserved: ' + name)
    for name, fingerprint in sorted(files.items()):
        path = destination / name
        if not path.exists():
            raise InstallError('Existing installation is incomplete; files were preserved: ' + name)
        if _file_fingerprint(path) != fingerprint:
            raise InstallError('Existing installation differs from this version; files were preserved: ' + name)


def install(*, archive=None, url=None, sha256, destination=None, run_setup=False,
            reuse_verified=False):
    if (archive is None) == (url is None):
        raise InstallError('Provide exactly one archive path or release URL')
    destination = _absolute(destination) if destination is not None else _default_destination()
    _check_components(destination)
    existing = destination.exists()
    if existing and not reuse_verified:
        raise InstallError('Destination already exists; no files were replaced')
    _mkdir_parents(destination.parent)
    executable = None
    with tempfile.TemporaryDirectory(prefix='.ac-deck-stage-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        downloaded = stage / 'release.tar.gz'
        _stage_archive(archive, url, downloaded, sha256)
        _extract_archive(downloaded, stage)
        source = stage / ROOT_NAME
        expected = _inventory(source)
        if existing:
            _verify_existing(destination, expected)
        else:
            _publish(source, destination)
        if (_inventory(source) != expected
                or (not existing and _inventory(destination) != expected)):
            raise InstallError('Installed files differ from the verified archive; directory was preserved: '
                               + str(destination))
        executable = expected[1]['ac-deck']
    if run_setup:
        if _file_fingerprint(destination / 'ac-deck') != executable:
            raise InstallError('Installed executable changed; setup was not started')
        _run_setup(destination)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--archive', type=Path, help='Local release archive')
    source.add_argument('--url', help='HTTPS URL of a published community release')
    parser.add_argument('--sha256', required=True, help='SHA-256 from a trusted release source')
    parser.add_argument('--destination', type=Path, help='New absolute directory (default: XDG data home/ac-deck)')
    parser.add_argument('--run-setup', action='store_true', help='Run ac-deck install after verification')
    parser.add_argument('--accept-terms', action='store_true',
                        help='Explicitly agree to the installation terms without an interactive prompt')
    parser.add_argument('--reuse-verified', action='store_true',
                        help='Rerun setup only if all existing distribution files match this archive')
    args = parser.parse_args(argv)
    try:
        if not args.accept_terms and not _confirm_terms():
            raise InstallError('Terms were not accepted; installation was not started')
        destination = install(archive=args.archive, url=args.url, sha256=args.sha256,
                              destination=args.destination, run_setup=args.run_setup,
                              reuse_verified=args.reuse_verified)
    except (KeyboardInterrupt, EOFError):
        print('Installation cancelled; terms were not accepted', file=sys.stderr)
        return 1
    except (InstallError, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        print('Installation stopped: ' + str(error), file=sys.stderr)
        return 1
    print('Installed to ' + str(destination))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
