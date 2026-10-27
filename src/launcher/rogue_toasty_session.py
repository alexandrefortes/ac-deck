"""Canal local exclusivo do Toasty; sem contadores esportivos ou resumo de observação.

OMTL1: token, generation, seq, physics_ms, flags, session_start_total,
restart_total, last_event_restart. Só o contexto necessário para autorizar o efeito.
OMT1/OMTG1 e as reservas por corrida conservam seus contratos.
"""
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import time

from . import file_io as safe

PROTOCOL = 'OMTL1'
ENDPOINT_VERSION = 'OMTE1'
FLAG_PHYSICS, FLAG_PAUSED, FLAG_REPLAY = 1, 2, 4
FLAG_MENU, FLAG_STARTED, FLAG_FINISHED = 8, 16, 32
MAX_INTEGER = 2**53 - 1
MAX_PACKET_BYTES = 256
MAX_FILE_BYTES = 4096
MAX_GENERATIONS = 16
MAX_BATCH = 64
STALE_SECONDS = 1.0
METADATA_KEYS = ('run_id', 'challenge_id', 'attempt_id', 'session_id')


def _metadata(value):
    if not isinstance(value, dict) or set(value) != set(METADATA_KEYS):
        raise ValueError('Toasty metadata differs')
    result = {}
    for key in METADATA_KEYS:
        item = value[key]
        if not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', item):
            raise ValueError('Invalid Toasty identity')
        result[key] = item
    return result


def _integer(value, low=0, high=MAX_INTEGER):
    if not re.fullmatch(r'0|[1-9][0-9]*|-1', value):
        raise ValueError('Invalid Toasty integer')
    number = int(value)
    if not low <= number <= high:
        raise ValueError('Toasty integer outside range')
    return number


def _stamp(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1e12:
        raise ValueError('Invalid Toasty physics time')
    return number


def _read(path, limit):
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size > limit:
            raise ValueError('Toasty file too large')
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    if (len(data) > limit or safe.signature(before) != safe.signature(after)
            or safe.signature(after) != safe.signature(current)):
        raise RuntimeError('Toasty file changed during reading')
    return data, safe.signature(current)


class _OwnedFile:
    """Só substitui/remove o inode e conteúdo exatos criados por este objeto."""
    def __init__(self, path, data):
        self.path, self.data, self.signature = Path(path), None, None
        self.write(data)

    def verify(self):
        data, signature = _read(self.path, MAX_FILE_BYTES)
        if signature != self.signature or data != self.data:
            raise RuntimeError('Toasty file belongs to another owner or was modified')

    def write(self, data):
        safe.check_components(self.path)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('Toasty file too large')
        if self.signature is None:
            try:
                self.path.lstat()
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError('Toasty file already exists')
        else:
            self.verify()
        temporary = self.path.with_name(self.path.name + '.' + secrets.token_hex(16) + '.new')
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, 'O_NOFOLLOW', 0), 0o600)
        opened_temporary = os.fstat(descriptor)
        temporary_identity = opened_temporary.st_dev, opened_temporary.st_ino
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            safe.check_components(self.path)
            if self.signature is None:
                # Publicação sem sobrescrever quem surgiu durante a gravação.
                os.link(temporary, self.path, follow_symlinks=False)
                temporary.unlink()
            else:
                self.verify()
                temporary.replace(self.path)
            self.data, self.signature = _read(self.path, MAX_FILE_BYTES)
            if self.data != data:
                raise RuntimeError('Toasty file changed during publication')
        finally:
            # Este nome aleatório pertence somente à gravação atual.
            try:
                safe.check_components(temporary)
                info = temporary.lstat()
                if (not safe.linked(info) and info.st_nlink == 1
                        and (info.st_dev, info.st_ino) == temporary_identity):
                    temporary.unlink()
            except (OSError, ValueError, RuntimeError):
                pass

    def remove(self):
        try:
            self.verify()
            safe.check_components(self.path)
            if safe.signature(self.path.lstat()) != self.signature:
                return False
            self.path.unlink()
            return True
        except FileNotFoundError:
            return True
        except (OSError, ValueError, RuntimeError):
            return False


def _encode(data):
    raw = (json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('ascii')
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('Toasty summary too large')
    return raw


def decode(raw, token):
    if not isinstance(raw, bytes) or len(raw) > MAX_PACKET_BYTES:
        raise ValueError('Toasty context too large')
    parts = raw.decode('ascii').split('|')
    if (len(parts) != 9 or parts[0] != PROTOCOL or parts[1] != token
            or not re.fullmatch(r'[a-f0-9]{32}', token)
            or not re.fullmatch(r'[a-f0-9]{16}', parts[2])):
        raise ValueError('Toasty context identity differs')
    frame = dict(generation=parts[2], seq=_integer(parts[3], 1), physics_ms=_stamp(parts[4]),
                 flags=_integer(parts[5], 0, 63), session_start_total=_integer(parts[6]),
                 restart_total=_integer(parts[7]), last_event_restart=_integer(parts[8], 0, 1))
    if (frame['restart_total'] > frame['session_start_total']
            or frame['last_event_restart'] and not frame['restart_total']):
        raise ValueError('Invalid Toasty restart context')
    return frame


class Session:
    """Receptor por tentativa sob active.lock; endpoints antigos não são reutilizados."""
    def __init__(self, package_dir, metadata, *, clock=time.monotonic):
        self.metadata = _metadata(metadata)
        package = safe.source_root(package_dir)
        state = safe.source_root(package / 'launcher')
        self.history = safe.source_root(state / 'sessions' / self.metadata['session_id'])
        self.endpoint_path = self.history / 'rogue-toasty-endpoint.txt'
        self.clock, self.token = clock, secrets.token_hex(16)
        self._now = _stamp(str(clock()))
        self.socket = self._endpoint = None
        self._latest = self._latest_peer = self._received_at = self._progress_at = None
        self._generations = set()
        self._race, self._reservation = 0, None
        self._closed = False
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('127.0.0.1', 0))
            self.socket.setblocking(False)
            body = f'{ENDPOINT_VERSION}\n{self.socket.getsockname()[1]}\n{self.token}\n{self.metadata["attempt_id"]}\n'
            self._endpoint = _OwnedFile(self.endpoint_path, body.encode('ascii'))
        except BaseException:
            if self.socket is not None:
                self.socket.close()
                self.socket = None
            if self._endpoint is not None:
                self._endpoint.remove()
            raise

    @staticmethod
    def _active(frame):
        flags = frame['flags']
        return bool(flags & FLAG_PHYSICS and flags & FLAG_STARTED and
                    not flags & (FLAG_PAUSED | FLAG_REPLAY | FLAG_MENU | FLAG_FINISHED))

    def _accept(self, frame, peer):
        previous = self._latest
        generation = frame['generation']
        changed = previous is None or generation != previous['generation']
        if changed:
            if generation in self._generations or len(self._generations) >= MAX_GENERATIONS:
                return
            self._generations.add(generation)
        else:
            if peer != self._latest_peer or frame['seq'] <= previous['seq']:
                return
            if any(frame[key] < previous[key] for key in ('session_start_total', 'restart_total')):
                return
            if (frame['session_start_total'] == previous['session_start_total']
                    and frame['last_event_restart'] != previous['last_event_restart']):
                return
            if (frame['session_start_total'] > previous['session_start_total']
                    and frame['restart_total'] > previous['restart_total'] and frame['last_event_restart']):
                self._race += 1
                self._reservation = None
        if (changed or not self._active(frame) or not self._active(previous)
                or frame['physics_ms'] < previous['physics_ms']):
            self._progress_at = None
        elif frame['physics_ms'] > previous['physics_ms']:
            self._progress_at = self._now
        self._latest, self._latest_peer, self._received_at = frame, peer, self._now

    def _claim(self, raw, peer):
        from . import rogue_toasty
        request = rogue_toasty.decode_request(raw, self.token)
        latest = self._latest
        if (latest is None or peer != self._latest_peer or not self._active(latest)
                or self._now - self._received_at > STALE_SECONDS or self._progress_at is None
                or self._now - self._progress_at > STALE_SECONDS
                or request['generation'] != latest['generation']
                or request['session_start_total'] != latest['session_start_total']
                or not 0 <= latest['physics_ms'] - request['physics_ms'] <= rogue_toasty.REQUEST_WINDOW_MS):
            return
        if self._reservation is None:
            name = 'rogue-toasty.json' if self._race == 0 else f'rogue-toasty-restart-{self._race}.json'
            self._reservation = rogue_toasty.Reservation(self.history / name, self.metadata)
        granted = self._reservation.reserve(request)
        self.socket.sendto(rogue_toasty.encode_grant(self.token, request, granted), peer)

    def tick(self):
        if self._closed:
            return
        now = _stamp(str(self.clock()))
        if now < self._now:
            self._progress_at = None
            return
        self._now = now
        for _ in range(MAX_BATCH):
            try:
                raw, peer = self.socket.recvfrom(MAX_PACKET_BYTES + 1)
            except BlockingIOError:
                break
            if peer[0] != '127.0.0.1':
                continue
            try:
                if raw.startswith(b'OMT1|'):
                    self._claim(raw, peer)
                else:
                    self._accept(decode(raw, self.token), peer)
            except (OSError, ValueError, RuntimeError):
                # Efeito indisponível nunca interrompe a corrida ou muda progresso.
                continue

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        if self._endpoint is not None:
            self._endpoint.remove()
