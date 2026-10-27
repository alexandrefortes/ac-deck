"""Reserva cosmética local, persistida antes de autorizar Toasty no HUD CSP.

OMT1 (ASCII, exatamente seis campos):
  OMT1|token32hex|generation16hex|request_id|session_start_total|physics_ms
OMTG1 (ASCII, exatamente cinco campos):
  OMTG1|token32hex|generation16hex|request_id|0ou1

O produtor mantém o pedido imutável por até 0,75 s. A Session autentica e confere
telemetria viva/fresca antes de consultar esta reserva. Pedido não é telemetria,
não comprova infração e nunca renova frescor. Uma reserva gasta a única vaga da
corrida, mesmo que grant/efeito se percam; não há ACK, cooldown global, worker,
áudio, desenho, escrita Lua ou alteração de resultado/XP/vidas neste módulo.
"""
from copy import deepcopy
import json
import os
import re

from . import file_io as safe
from . import rogue_toasty_session as support

REQUEST_PROTOCOL = 'OMT1'
GRANT_PROTOCOL = 'OMTG1'
MAX_REQUEST_BYTES = 256
MAX_LEDGER_BYTES = 4096
REQUEST_WINDOW_MS = 750.0
REQUEST_FIELDS = ('generation', 'request_id', 'session_start_total', 'physics_ms')


def _sync_parent(path):
    """Confirma também a publicação do nome antes de emitir uma autorização."""
    safe.check_components(path)
    before = path.lstat()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError('Toasty ledger directory changed')
        os.fsync(descriptor)
        safe.check_components(path)
        after = path.lstat()
        if (opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino):
            raise RuntimeError('Toasty ledger directory changed')
    finally:
        os.close(descriptor)


def decode_request(raw, token):
    """Somente identidade numérica limitada; token errado não produz resposta."""
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError('Toasty request too large')
    parts = raw.decode('ascii').split('|')
    if (len(parts) != 6 or parts[0] != REQUEST_PROTOCOL or parts[1] != token
            or not re.fullmatch(r'[a-f0-9]{32}', token)
            or not re.fullmatch(r'[a-f0-9]{16}', parts[2])
            or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', parts[5])):
        raise ValueError('Toasty request identity differs')
    return dict(generation=parts[2], request_id=support._integer(parts[3], 1),
                session_start_total=support._integer(parts[4]), physics_ms=support._stamp(parts[5]))


def encode_grant(token, request, granted):
    """Resposta sem texto livre; a geração/ID permitem ignorar grants atrasados."""
    # Revalida inclusive chamadas internas antes de interpolar campos no fio.
    _request(request)
    if not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{32}', token):
        raise ValueError('Invalid Toasty token')
    if type(granted) is not bool:
        raise ValueError('Invalid Toasty grant state')
    return f'{GRANT_PROTOCOL}|{token}|{request["generation"]}|{request["request_id"]}|{int(granted)}'.encode('ascii')


def _request(value):
    if not isinstance(value, dict) or set(value) != set(REQUEST_FIELDS):
        raise ValueError('Invalid Toasty request fields')
    if not isinstance(value['generation'], str) or not re.fullmatch(r'[a-f0-9]{16}', value['generation']):
        raise ValueError('Invalid Toasty generation')
    for key, minimum in (('request_id', 1), ('session_start_total', 0)):
        if type(value[key]) is not int or not minimum <= value[key] <= support.MAX_INTEGER:
            raise ValueError('Invalid Toasty request counter')
    if type(value['physics_ms']) not in (int, float):
        raise ValueError('Invalid Toasty request time')
    support._stamp(str(value['physics_ms']))
    return deepcopy(value)


def _ledger(raw, metadata):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate Toasty ledger key')
            result[key] = value
        return result
    data = json.loads(raw.decode('ascii'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite Toasty ledger')))
    if (not isinstance(data, dict) or set(data) != {
            'schema_version', 'grant_protocol', 'cosmetic_only', 'metadata', 'reserved', *REQUEST_FIELDS}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['grant_protocol'] != GRANT_PROTOCOL or data['cosmetic_only'] is not True
            or data['reserved'] is not True or data['metadata'] != metadata):
        raise ValueError('Toasty ledger identity or schema differs')
    _request({key: data[key] for key in REQUEST_FIELDS})
    return data


class Reservation:
    """Uma criação atômica por corrida; reinícios usam outro arquivo exclusivo."""
    def __init__(self, path, metadata):
        self.path = safe.absolute(path)
        if not re.fullmatch(r'rogue-toasty(?:-restart-[1-9][0-9]{0,15})?\.json', self.path.name):
            raise ValueError('Invalid Toasty ledger path')
        safe.source_root(self.path.parent)
        self.metadata = support._metadata(metadata)
        self._data = self._raw = self._signature = None
        self._blocked = False
        try:
            self._load()
        except FileNotFoundError:
            pass
        except (OSError, ValueError, RuntimeError, RecursionError):
            # Arquivo desconhecido/modificado permanece intacto; efeito suprimido.
            self._blocked = True

    def _load(self):
        raw, signature = support._read(self.path, MAX_LEDGER_BYTES)
        data = _ledger(raw, self.metadata)
        self._data, self._raw, self._signature = data, raw, signature

    def reserve(self, request):
        """True só após persistência ou reenvio da mesma reserva íntegra."""
        request = _request(request)
        if self._blocked:
            return False
        if self._data is not None:
            try:
                raw, signature = support._read(self.path, MAX_LEDGER_BYTES)
                if raw != self._raw or signature != self._signature:
                    self._blocked = True
                    return False
            except (OSError, ValueError, RuntimeError):
                self._blocked = True
                return False
            try:
                _sync_parent(self.path.parent)
            except (OSError, ValueError, RuntimeError):
                self._blocked = True
                return False
            return all(self._data[key] == request[key] for key in REQUEST_FIELDS)
        data = dict(schema_version=1, grant_protocol=GRANT_PROTOCOL, cosmetic_only=True,
                    metadata=deepcopy(self.metadata), reserved=True, **request)
        try:
            owner = support._OwnedFile(self.path, support._encode(data))
            _sync_parent(self.path.parent)
            self._data, self._raw, self._signature = data, owner.data, owner.signature
            return True
        except FileExistsError:
            # Outra instância ganhou a criação exclusiva. Só relê, nunca sobrescreve.
            try:
                self._load()
                _sync_parent(self.path.parent)
                return all(self._data[key] == request[key] for key in REQUEST_FIELDS)
            except (OSError, ValueError, RuntimeError, RecursionError):
                self._blocked = True
                return False
        except (OSError, ValueError, RuntimeError):
            self._blocked = True
            return False
