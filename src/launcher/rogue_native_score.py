"""Read the native Time Attack and Drift scores for one known PE image."""

from bisect import bisect_right
from contextlib import ExitStack
from dataclasses import dataclass
import math
import os
from pathlib import Path
import struct
import sys

from . import file_io, session_process


# Offsets and score representation are specific to this SHA-256. See
# docs/pontuacao-eventos-nativos.md for the native consumers and object graph.
SUPPORTED_SHA256 = '0df569c840f8303f7018f7891085e3a4c22cf93fb19327c6a0b85325cea23fd1'
_IMAGE_SIZE = 0x15E1000
_HEADER_SIZE = 0x400
_CODE_RVA = 0x18C820
_CODE = bytes.fromhex('48 8b 05 e1 d3 3c 01 c3')
_CONSOLE_SLOT = 0x1559C08
_MODES = {
    0x4DC990: ('time_attack', 0x240, 0x284, 0x2B8),
    0x4B3848: ('drift', 0xE0, 0x290, 0xD8),
}
_MAX_COMPONENTS = 256


class _Unavailable(Exception):
    pass


def _flags():
    return os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW


def _read_proc(dirfd, name, limit):
    fd = os.open(name, _flags(), dir_fd=dirfd)
    try:
        data = bytearray()
        while chunk := os.read(fd, limit + 1 - len(data)):
            data.extend(chunk)
            if len(data) > limit:
                raise _Unavailable('incomplete_process_metadata')
        if data and not data.endswith(b'\n'):
            raise _Unavailable('incomplete_process_metadata')
        return bytes(data)
    finally:
        os.close(fd)


def _read_memory(fd, address, size):
    data = os.pread(fd, size, address)
    if len(data) != size:
        raise _Unavailable('incomplete_memory_read')
    return data


def _check_stat(dirfd, expected):
    fields = _read_proc(dirfd, 'stat', 4096).rsplit(b')', 1)[-1].split()
    if (len(fields) < 20 or fields[0] in (b'Z', b'X', b'x')
            or int(fields[1]) != expected[0] or int(fields[19]) != expected[2]):
        raise _Unavailable('process_changed')


@dataclass(frozen=True)
class _Region:
    start: int
    end: int
    permissions: bytes
    offset: int
    device: tuple[int, int]
    inode: int
    deleted: bool


class _Maps:
    def __init__(self, dirfd):
        self.regions = []
        for line in _read_proc(dirfd, 'maps', 1024 * 1024).splitlines():
            address, permissions, offset, device, inode, *path = line.split(None, 5)
            start, end = (int(part, 16) for part in address.split(b'-'))
            major, minor = (int(part, 16) for part in device.split(b':'))
            if start >= end or (self.regions and start < self.regions[-1].end):
                raise _Unavailable('incomplete_process_metadata')
            self.regions.append(_Region(start, end, permissions, int(offset, 16),
                                        (major, minor), int(inode),
                                        bool(path and path[0].endswith(b' (deleted)'))))
        self.starts = [region.start for region in self.regions]

    def contains(self, address, size, permission=b'r'):
        index = bisect_right(self.starts, address) - 1
        return (index >= 0 and 0 < address < address + size <= self.regions[index].end
                and all(flag in self.regions[index].permissions for flag in permission))

    def bases(self, info):
        device = os.major(info.st_dev), os.minor(info.st_dev)
        return [region.start for region in self.regions
                if region.device == device and region.inode == info.st_ino
                and not region.deleted and region.offset == 0
                and self.contains(region.start, _HEADER_SIZE)
                and self.contains(region.start + _CODE_RVA, len(_CODE), b'rx')
                and self.contains(region.start + _CONSOLE_SLOT, 8)]


def _file_identity(info):
    return file_io.signature(info), info.st_ctime_ns, info.st_nlink


def _pe_header(data):
    if len(data) != _HEADER_SIZE or data[:2] != b'MZ':
        return None
    pe, = struct.unpack_from('<I', data, 0x3C)
    optional = pe + 24
    if (pe < 0x40 or optional + 60 > len(data)
            or data[pe:pe + 6] != b'PE\0\0\x64\x86'
            or data[optional:optional + 2] != b'\x0b\x02'
            or struct.unpack_from('<I', data, optional + 56)[0] != _IMAGE_SIZE):
        return None
    # Wine can update the PE32+ ImageBase when it relocates the image.
    base = optional + 24
    return data[:base] + data[base + 8:]


def _score_snapshot(read, base):
    def pointer(address):
        return struct.unpack('<Q', read(address, 8))[0]

    console = pointer(base + _CONSOLE_SLOT)
    if pointer(console) != base + 0x4D6630:
        raise _Unavailable('waiting_score')
    sim = pointer(console + 0x68)
    if pointer(sim) != base + 0x4D8010 or pointer(sim + 0x228) != console:
        raise _Unavailable('waiting_score')
    game = pointer(sim + 0x8)
    if pointer(game) != base + 0x4F0C38 or read(game + 0x270, 1) != b'\0':
        raise _Unavailable('waiting_score')
    root = pointer(game + 0x178)
    if not root or pointer(sim + 0x38) != root:
        raise _Unavailable('waiting_score')

    begin, end, capacity = struct.unpack('<QQQ', read(sim + 0x40, 24))
    if (begin % 8 or end % 8 or capacity % 8 or not begin < end <= capacity
            or capacity - begin > 8 * _MAX_COMPONENTS):
        raise _Unavailable('waiting_score')
    slots = tuple(slot for (slot,) in struct.iter_unpack('<Q', read(begin, end - begin)))
    cars, cars_end = struct.unpack('<QQ', read(sim + 0x208, 16))
    if cars % 8 or cars_end % 8 or not 0 < cars < cars_end:
        raise _Unavailable('waiting_score')
    player = pointer(cars)
    if pointer(player) != base + 0x4BE5E8 or pointer(player + 0x130) != sim:
        raise _Unavailable('waiting_score')

    matches = []
    for slot in slots:
        definition = _MODES.get(pointer(slot) - base)
        if definition is not None:
            matches.append((slot, definition))
    if len(matches) != 1:
        raise _Unavailable('waiting_score')
    event, (mode, car_offset, score_offset, state_offset) = matches[0]
    if pointer(event + 0x38) != sim or pointer(event + car_offset) != player:
        raise _Unavailable('waiting_score')
    state, = struct.unpack('<i', read(event + state_offset, 4))
    if state not in (0, 1):
        raise _Unavailable('waiting_score')
    score = read(event + score_offset, 4)
    if read(game + 0x270, 1) != b'\0':
        raise _Unavailable('waiting_score')
    identity = console, sim, game, root, player, event
    vectors = begin, end, capacity, slots, cars, cars_end
    return identity, vectors, mode, state, score


class Reader:
    """Optional diagnostics for descendants of the supplied Linux launch.

    The caller polls Session before sampling and calls close at shutdown.
    Only an 'ok' sample carries points and sets the sample metadata.
    """

    def __init__(self, game_exe: Path, session: session_process.Session, mode: str | None = None):
        self.game_exe = game_exe
        self.session = session
        self.mode = mode
        self.active_mode = None
        self.sample_identity = None
        self.sample_finished = False
        self._binding = None
        self._active_event = None
        self._descriptors = ExitStack()
        self._reference = None
        self._disabled = None
        if sys.platform != 'linux':
            self._disabled = 'unsupported_platform'
        elif mode is not None and mode not in ('time_attack', 'drift'):
            self._disabled = 'unsupported_mode'

    def _load_reference(self):
        try:
            digest, info = file_io.hash_reference_file(self.game_exe)
            if digest != SUPPORTED_SHA256:
                raise _Unavailable('unsupported_executable')
            stream, opened = file_io.open_reference(self.game_exe)
            with stream:
                header = _pe_header(stream.read(_HEADER_SIZE))
                if header is None or _file_identity(opened) != _file_identity(os.fstat(stream.fileno())):
                    raise _Unavailable('unsupported_executable')
            if _file_identity(info) != _file_identity(opened):
                raise _Unavailable('unsupported_executable')
            self._reference = info, header
        except (OSError, file_io.SafetyError, _Unavailable):
            self._disabled = 'unsupported_executable'
            raise _Unavailable(self._disabled) from None

    def _lineage(self, pid, live):
        ancestors = {}
        while pid in live and pid not in ancestors:
            row = live[pid]
            if pid in self.session.before and self.session.before[pid][2] == row[2]:
                return None
            ancestors[pid] = row
            if pid == self.session.pid:
                return ancestors if row[0] == os.getpid() else None
            pid = row[0]
        return None

    def _connect(self, live, info):
        with ExitStack() as selected:
            match = None
            denied = False
            for pid in live:
                lineage = self._lineage(pid, live)
                if lineage is None:
                    continue
                with ExitStack() as probe:
                    try:
                        proc = os.open(f'/proc/{pid}', _flags() | os.O_DIRECTORY)
                        probe.callback(os.close, proc)
                        _check_stat(proc, lineage[pid])
                        bases = _Maps(proc).bases(info)
                    except PermissionError:
                        denied = True
                        continue
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    if not bases:
                        continue
                    if match is not None or len(bases) != 1:
                        raise _Unavailable('ambiguous_process')
                    selected.callback(probe.pop_all().close)
                    match = pid, proc, bases[0], lineage
            if match is None:
                raise _Unavailable('access_denied' if denied else 'waiting_process')
            pid, proc, base, lineage = match
            for ancestor, row in lineage.items():
                if ancestor == pid:
                    _check_stat(proc, row)
                    continue
                fd = os.open(f'/proc/{ancestor}', _flags() | os.O_DIRECTORY)
                try:
                    _check_stat(fd, row)
                finally:
                    os.close(fd)
            memory = os.open('mem', _flags(), dir_fd=proc)
            selected.callback(os.close, memory)
            _check_stat(proc, lineage[pid])
            self._descriptors = selected.pop_all()
            self._binding = pid, lineage[pid][2], proc, memory, base

    def _disconnect(self):
        self._binding = None
        self._active_event = None
        self._descriptors.close()

    def sample(self) -> tuple[str, int | None]:
        self.active_mode = None
        self.sample_identity = None
        self.sample_finished = False
        if self._disabled is not None:
            return self._disabled, None
        try:
            return self._sample()
        except _Unavailable as error:
            if str(error) not in ('waiting_score', 'score_changed', 'invalid_score'):
                self._disconnect()
            elif str(error) != 'score_changed':
                self._active_event = None
            return str(error), None
        except PermissionError:
            self._disconnect()
            return 'access_denied', None
        except (OSError, ValueError, struct.error):
            self._disconnect()
            return 'read_failed', None

    def _sample(self):
        with self.session.lock:
            live = dict(self.session.live)
            stopping = self.session.stop_at is not None
        if stopping or not live:
            self._disconnect()
            return 'waiting_process', None
        if self._reference is None:
            self._load_reference()
        info, header = self._reference
        if _file_identity(info) != _file_identity(self.game_exe.lstat()):
            self._disabled = 'unsupported_executable'
            raise _Unavailable(self._disabled)
        if self._binding is None:
            self._connect(live, info)
        pid, start, proc, memory, base = self._binding
        lineage = self._lineage(pid, live)
        if lineage is None or lineage[pid][2] != start:
            raise _Unavailable('process_changed')
        _check_stat(proc, lineage[pid])
        maps = _Maps(proc)
        if maps.bases(info) != [base]:
            raise _Unavailable('image_changed')
        if (_pe_header(_read_memory(memory, base, _HEADER_SIZE)) != header
                or _read_memory(memory, base + _CODE_RVA, len(_CODE)) != _CODE):
            raise _Unavailable('image_changed')

        def read(address, size):
            if address % min(size, 8) or not maps.contains(address, size):
                raise _Unavailable('waiting_score')
            return _read_memory(memory, address, size)

        observed = _score_snapshot(read, base)
        confirmed = _score_snapshot(read, base)
        if observed[:-1] != confirmed[:-1]:
            self._active_event = None
            raise _Unavailable('score_changed')
        if observed[-1] != confirmed[-1]:
            raise _Unavailable('score_changed')
        if _read_memory(memory, base + _CODE_RVA, len(_CODE)) != _CODE:
            raise _Unavailable('image_changed')
        _check_stat(proc, lineage[pid])
        identity, _, mode, state, raw = observed
        if self.mode is not None and mode != self.mode:
            raise _Unavailable('waiting_score')
        points, = struct.unpack('<f', raw)
        if not math.isfinite(points) or not -(2 ** 31) <= points < 2 ** 31:
            raise _Unavailable('invalid_score')
        event = identity, mode
        if state == 0 and self._active_event != event:
            raise _Unavailable('waiting_score')
        self._active_event = event
        self.active_mode = mode
        self.sample_identity = pid, start, base, event
        self.sample_finished = state == 0
        return 'ok', int(points)

    def close(self):
        self.active_mode = None
        self.sample_identity = None
        self.sample_finished = False
        self._disabled = 'closed'
        self._disconnect()
