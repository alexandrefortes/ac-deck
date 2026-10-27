"""Runs Rogue locais, com resultados correlacionados e recompensas idempotentes."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import uuid

from . import file_io as safe
from . import content, results, rogue_rewards, session_settings


FILE_LIMIT = 8 * 1024 * 1024
COMPACT_AT = 1024 * 1024
RECENT_ATTEMPTS = 100
MAX_LIVES = 3
XP_PER_CHALLENGE = 100
PARTIAL_XP = 20
MARKER = 'rogue'
_BADGES = rogue_rewards.badge_definitions()
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def path_for(synthesis_store):
    return Path(synthesis_store).parent / 'rogue.json'


def _integer(value, low=0, high=2**53 - 1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid Rogue number.')
    return value


def _identity(value):
    return content.identifier(value)


def _track_key(selection):
    return selection['track'] + '|' + selection.get('layout', '')


def stage(run):
    wins = _integer(run.get('wins', 0))
    value = _integer(run.get('stage', wins + 1), 1)
    if value < wins + 1:
        raise ValueError('Invalid Rogue stage.')
    return value


def _selection(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid Rogue race configuration.')
    for key in ('car', 'track', 'skin'):
        _identity(value.get(key))
    content.identifier(value.get('layout', ''), empty=True)
    _integer(value.get('mode'), 2, 2)
    if value.get('event', '') != '':
        raise ValueError('Rogue requires a standalone race.')
    _integer(value.get('opponents'), 1, 47)
    _integer(value.get('laps'), 1, 99)
    _integer(value.get('ai'), 70, 100)
    _integer(value.get('time_minutes'), 480, 960)
    return value


def _challenge(value, stage=None):
    if not isinstance(value, dict):
        raise ValueError('Invalid Rogue challenge.')
    _identity(value.get('challenge_id'))
    _integer(value.get('stage'), 1)
    if stage is not None and value['stage'] != stage:
        raise ValueError('Rogue challenge belongs to another stage.')
    selection = _selection(value.get('selection'))
    _integer(value.get('target_position'), 1, selection['opponents'] + 1)
    if not isinstance(value.get('base'), dict):
        raise ValueError('Rogue challenge base is missing.')
    if value.get('generator') not in ('deterministic', 'ai'):
        raise ValueError('Invalid Rogue generator.')
    if not isinstance(value.get('brief'), str) or len(value['brief']) > 4096:
        raise ValueError('Invalid Rogue challenge description.')
    return value


def _sticker_outcome(value):
    # Recibos legados não possuem o campo. Quando presente, não aceitar um ID
    # desconhecido que poderia reaparecer ao retornar um resultado idempotente.
    if isinstance(value, dict) and 'new_stickers' in value:
        rogue_rewards.validate_sticker_ids(value['new_stickers'])


def clean(value=None):
    if value is None:
        return dict(schema_version=1, profile=dict(car_xp={}, track_xp={}, track_wins={}, badges=[], stickers=[], best_wins=0,
                    processed_sessions={}), run=None)
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported Rogue progress file. Original file kept.')
    if set(value) != {'schema_version', 'profile', 'run'}:
        raise ValueError('Invalid Rogue progress file. Original file kept.')
    value = deepcopy(value)
    profile = value['profile']
    if not isinstance(profile, dict):
        raise ValueError('Invalid Rogue profile.')
    for key in ('car_xp', 'track_xp', 'track_wins'):
        mapping = profile.get(key)
        if not isinstance(mapping, dict):
            raise ValueError('Invalid Rogue XP.')
        for identity, amount in mapping.items():
            if key == 'car_xp':
                _identity(identity)
            else:
                if not isinstance(identity, str) or identity.count('|') != 1:
                    raise ValueError('Invalid Rogue track XP identity.')
                track, layout = identity.split('|')
                _identity(track)
                content.identifier(layout, empty=True)
            _integer(amount)
    _integer(profile.get('best_wins'))
    if (not isinstance(profile.get('badges'), list)
            or any(not isinstance(identity, str) for identity in profile['badges'])
            or len(set(profile['badges'])) != len(profile['badges'])
            or any(identity not in {row[0] for row in _BADGES} for identity in profile['badges'])):
        raise ValueError('Invalid Rogue album.')
    # Legado 079–081 não possui stickers. IDs presentes são validados antes de
    # qualquer backfill; conteúdo desconhecido bloqueia sem descartar o original.
    profile['stickers'] = rogue_rewards.validate_sticker_ids(profile.get('stickers', []))
    receipts = profile.get('processed_sessions')
    if not isinstance(receipts, dict):
        raise ValueError('Invalid Rogue result receipts.')
    for session_id, receipt in receipts.items():
        _identity(session_id)
        if not isinstance(receipt, dict) or not isinstance(receipt.get('attempt_id'), str):
            raise ValueError('Invalid Rogue result receipt.')
        _identity(receipt['attempt_id'])
        _sticker_outcome(receipt)
    if 'archive_id' in profile:
        identity = profile['archive_id']
        if (not isinstance(identity, str) or len(identity) != 32
                or any(char not in '0123456789abcdef' for char in identity)):
            raise ValueError('Invalid Rogue archive identity.')
    run = value['run']
    if run is not None:
        if not isinstance(run, dict):
            raise ValueError('Invalid Rogue run.')
        _identity(run.get('id'))
        _integer(run.get('seed'), 0, 2**64 - 1)
        if run.get('mode') not in ('deterministic', 'ai') or run.get('status') not in ('active', 'ended'):
            raise ValueError('Invalid Rogue run mode or status.')
        if not isinstance(run.get('base'), dict):
            raise ValueError('Invalid Rogue base.')
        for key in ('wins', 'streak'):
            _integer(run.get(key))
        stage(run)
        if run['streak'] > run['wins']:
            raise ValueError('Invalid Rogue streak.')
        _integer(run.get('lives'), 0, MAX_LIVES)
        if run.get('challenge') is not None:
            _challenge(run['challenge'], stage(run))
        if not isinstance(run.get('attempts'), dict) or not isinstance(run.get('history'), list):
            raise ValueError('Invalid Rogue attempt history.')
        for row in run['history']:
            if not isinstance(row, dict) or type(row.get('won')) is not bool:
                raise ValueError('Invalid Rogue challenge history.')
            _identity(row.get('car'))
            _identity(row.get('track'))
            content.identifier(row.get('layout', ''), empty=True)
            _identity(row.get('challenge_id'))
        if not isinstance(run.get('rewarded_badges'), list):
            raise ValueError('Invalid Rogue badge rewards.')
        if (any(not isinstance(identity, str) or identity not in {row[0] for row in _BADGES}
                for identity in run['rewarded_badges'])
                or len(set(run['rewarded_badges'])) != len(run['rewarded_badges'])):
            raise ValueError('Invalid Rogue badge rewards.')
        if 'challenge_xp' in run:
            _integer(run['challenge_xp'], 0, XP_PER_CHALLENGE)
        _integer(run.get('archived_xp', 0))
        rewards = run.get('archived_rewards', [])
        known = {row[0] for row in _BADGES} | set(rogue_rewards.sticker_ids())
        if (not isinstance(rewards, list) or any(not isinstance(item, str) or item not in known for item in rewards)
                or len(set(rewards)) != len(rewards)):
            raise ValueError('Invalid archived Rogue rewards.')
        _sticker_outcome(run.get('last_outcome'))
        for identity, attempt in run['attempts'].items():
            _identity(identity)
            if (not isinstance(attempt, dict) or attempt.get('id') != identity
                    or attempt.get('run_id') != run['id'] or attempt.get('status') not in ('pending', 'finished')):
                raise ValueError('Invalid Rogue attempt.')
            _identity(attempt.get('session_id'))
            _identity(attempt.get('challenge_id'))
            _selection(attempt.get('selection'))
            _integer(attempt.get('target_position'), 1, attempt['selection']['opponents'] + 1)
            _sticker_outcome(attempt.get('outcome'))
        pending = run.get('pending_attempt')
        if pending is not None and (not isinstance(pending, str) or pending not in run['attempts']
                                    or run['attempts'][pending]['status'] != 'pending'):
            raise ValueError('Invalid pending Rogue attempt.')
    # Strict encoding also rejects non-finite values in retained proposal fields.
    json.dumps(value, allow_nan=False)
    # Migração pura: XP já adquirido revela cosméticos, nunca vidas ou marcos de
    # sequência. load() não grava; a próxima mutação usa o save atômico normal.
    profile['stickers'].extend(rogue_rewards.newly_unlocked(profile, owned=profile['stickers']))
    return value


def load(path):
    path = safe.absolute(path)
    safe.check_components(path)
    if not path.exists():
        return clean()
    raw, _ = results._read(path)
    if len(raw) > FILE_LIMIT:
        raise ValueError('Rogue progress file is too large.')
    return clean(results._json(raw))


def _save(path, state):
    state = clean(state)
    raw = (json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > FILE_LIMIT:
        raise ValueError('Rogue progress file is too large.')
    safe.check_components(path)
    if path.exists():
        load(path)
    results._write(path, raw, replace=True)


def _sync(path, *, directory=False):
    safe.check_components(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                         | (getattr(os, 'O_DIRECTORY', 0) if directory else 0))
    try:
        if not directory:
            safe.require_reference(os.fstat(descriptor), path)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _archive_directory(path, profile, *, create=False):
    identity = profile.get('archive_id')
    if identity is None:
        if not create:
            return None
        identity = profile['archive_id'] = uuid.uuid4().hex
        parent = path.with_name(path.name + '.archive')
        safe.check_components(parent)
        parent.mkdir(mode=0o700, exist_ok=True)
        directory = parent / identity
        safe.check_components(directory)
        directory.mkdir(mode=0o700)
        results._save(directory / '_archive.json', dict(schema_version=1, archive_id=identity))
        _sync(directory / '_archive.json')
        _sync(directory, directory=True)
        _sync(parent, directory=True)
        _sync(path.parent, directory=True)
    directory = path.with_name(path.name + '.archive') / identity
    safe.check_components(directory)
    header = results._json(results._read(directory / '_archive.json')[0])
    if (not isinstance(header, dict) or type(header.get('schema_version')) is not int
            or header != dict(schema_version=1, archive_id=identity)):
        raise ValueError('Invalid Rogue archive. Original progress kept.')
    return directory


def _archived(path, profile, session_id):
    directory = _archive_directory(path, profile)
    if directory is None:
        return None
    _identity(session_id)
    try:
        row = results._json(results._read(directory / (session_id + '.json'))[0])
    except FileNotFoundError:
        return None
    if (not isinstance(row, dict)
            or set(row) != {'schema_version', 'archive_id', 'session_id', 'receipt', 'attempt'}
            or type(row['schema_version']) is not int or row['schema_version'] != 1
            or row['archive_id'] != profile['archive_id'] or row['session_id'] != session_id):
        raise ValueError('Invalid Rogue archived receipt. Original progress kept.')
    receipt, attempt = row['receipt'], row['attempt']
    if not isinstance(receipt, dict):
        raise ValueError('Invalid Rogue archived receipt.')
    _identity(receipt.get('attempt_id'))
    _sticker_outcome(receipt)
    if attempt is not None:
        if (not isinstance(attempt, dict) or attempt.get('status') != 'finished'
                or attempt.get('session_id') != session_id
                or attempt.get('id') != receipt['attempt_id'] or attempt.get('outcome') != receipt):
            raise ValueError('Invalid Rogue archived attempt.')
        _identity(attempt.get('run_id'))
        _identity(attempt.get('challenge_id'))
        _selection(attempt.get('selection'))
        _integer(attempt.get('target_position'), 1, attempt['selection']['opponents'] + 1)
    return row


def _compact(path, state):
    run = state['run']
    attempts = run['attempts'] if run else {}
    if (len(attempts) <= RECENT_ATTEMPTS
            and len(json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8')) < COMPACT_AT):
        return
    receipts = state['profile']['processed_sessions']
    keep = set(list(attempts)[-RECENT_ATTEMPTS:])
    if run:
        keep.add(run.get('pending_attempt'))
        keep.add((run.get('last_outcome') or {}).get('attempt_id'))
    removed = {identity: attempt for identity, attempt in attempts.items() if identity not in keep}
    keep_receipts = {attempt['session_id'] for identity, attempt in attempts.items() if identity in keep}
    sessions = set(receipts) - keep_receipts
    by_session = {attempt['session_id']: attempt for attempt in removed.values()}
    sessions.update(by_session)
    if not sessions:
        return
    directory = _archive_directory(path, state['profile'], create=True)
    for session_id in sorted(sessions):
        attempt = by_session.get(session_id)
        if attempt is not None and attempt.get('status') != 'finished':
            raise ValueError('Unfinished Rogue attempt cannot be archived.')
        receipt = receipts.get(session_id, attempt.get('outcome') if attempt else None)
        if not isinstance(receipt, dict) or not isinstance(receipt.get('attempt_id'), str):
            raise ValueError('Invalid Rogue result receipt. Original progress kept.')
        row = dict(schema_version=1, archive_id=state['profile']['archive_id'],
                   session_id=session_id, receipt=receipt, attempt=attempt)
        target = directory / (session_id + '.json')
        existing = _archived(path, state['profile'], session_id)
        if existing is None:
            results._save(target, row)
            if _archived(path, state['profile'], session_id) != row:
                raise ValueError('Rogue archived receipt differs. Original progress kept.')
        elif existing != row:
            raise ValueError('Rogue archived receipt differs. Original progress kept.')
        _sync(target)
    _sync(directory, directory=True)
    # O perfil só perde os registros depois de todas as cópias estarem publicadas.
    for session_id in sessions:
        receipts.pop(session_id, None)
    if run:
        rewards = set(run.get('archived_rewards', []))
        for identity, attempt in removed.items():
            outcome = attempt['outcome']
            run['archived_xp'] = run.get('archived_xp', 0) + _integer(outcome.get('xp_awarded', 0), 0, XP_PER_CHALLENGE)
            rewards.update(outcome.get('new_badges', []))
            rewards.update(outcome.get('new_stickers', []))
            del attempts[identity]
        run['archived_rewards'] = sorted(rewards)


def _profile_snapshot(path):
    """Bytes exatos e identidade para o reset explícito, sem seguir vínculos."""
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size > FILE_LIMIT:
            raise ValueError('Rogue progress file is too large.')
        raw = stream.read(FILE_LIMIT + 1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    signature = safe.signature(current)
    if (len(raw) > FILE_LIMIT or safe.signature(before) != safe.signature(after)
            or safe.signature(after) != signature):
        raise RuntimeError('Rogue profile changed during reset. Original file kept.')
    return raw, signature


def _backup_profile(path, raw):
    token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
    backup = path.with_name(path.name + '.profile-reset-' + token + '.bak')
    safe.check_components(backup)
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, 'O_NOFOLLOW', 0), 0o600)
    own_signature = safe.signature(os.fstat(descriptor))
    complete = False
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            try:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            finally:
                own_signature = safe.signature(os.fstat(stream.fileno()))
        copied, signature = _profile_snapshot(backup)
        if copied != raw or signature != own_signature:
            raise RuntimeError('Rogue backup changed during reset. Original file kept.')
        # O nome da cópia também deve estar publicado antes de substituir o perfil.
        safe.check_components(backup.parent)
        parent = backup.parent.stat()
        directory = os.open(backup.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) |
                            getattr(os, 'O_NOFOLLOW', 0))
        try:
            opened = os.fstat(directory)
            if (opened.st_dev, opened.st_ino) != (parent.st_dev, parent.st_ino):
                raise RuntimeError('Rogue backup directory changed.')
            os.fsync(directory)
        finally:
            os.close(directory)
        complete = True
        return backup
    finally:
        if not complete:
            # Limpa somente a cópia incompleta cujo inode ainda é o nosso.
            try:
                safe.check_components(backup)
                info = backup.lstat()
                safe.require_reference(info, backup)
                if safe.signature(info) == own_signature:
                    backup.unlink()
            except (OSError, ValueError, RuntimeError):
                pass


@contextmanager
def _locked(path):
    """Serializa instâncias do menu/coletor sem manter arquivos abertos na sessão."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(str(path), threading.RLock())
    with lock:
        safe.check_components(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_name(path.name + '.lock')
        safe.check_components(lock_path)
        if lock_path.exists():
            safe.require_reference(lock_path.lstat(), lock_path)
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            safe.require_reference(os.fstat(descriptor), lock_path)
            try:
                import fcntl
            except ImportError:
                fcntl = None
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)


def album(state):
    """Somente os dados revelados podem sair do núcleo para a interface."""
    acquired = clean(state)['profile']['badges']
    return [dict(id=identity if identity in acquired else None, unlocked=identity in acquired,
                 name=name if identity in acquired else 'Unknown badge',
                 description=description if identity in acquired else 'Keep driving to discover this badge.')
            for identity, _, name, description in _BADGES]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _active(state):
    run = state['run']
    if run is None or run['status'] != 'active':
        raise ValueError('Start a Rogue run first.')
    return run


def _summary(run, status, *, attempt=None, position=None, xp=0, badges=(), stickers=(), reason=''):
    return dict(status=status, attempt_id=attempt['id'] if attempt else None,
                challenge_id=attempt['challenge_id'] if attempt else None,
                position=position, target_position=attempt['target_position'] if attempt else None,
                xp_awarded=xp, lives=run['lives'], streak=run['streak'], wins=run['wins'],
                new_badges=list(badges), new_stickers=list(stickers), reason=reason,
                message={'won': 'Challenge won. Progress saved.',
                         'lost': 'Challenge lost. Continue to the next event.' if run['status'] == 'active' and run.get('challenge') is None else 'Challenge lost. Retry the same event.' if run['status'] == 'active' else 'Run ended. Your XP and achievements are kept.',
                         'unconfirmed': 'Result not confirmed. The same challenge is kept; no life was lost.',
                         'start_failed': 'Race could not start. The same challenge is kept; no life was lost.'}[status])


def _outcome(attempt, record):
    if not isinstance(record, dict) or type(record.get('schema_version')) is not int or record['schema_version'] != 1:
        raise ValueError('Invalid Rogue result record.')
    if record.get('session_id') != attempt['session_id']:
        raise ValueError('Rogue result belongs to another session.')
    if record.get('status') != 'imported':
        if record.get('status') not in ('pending', 'unavailable'):
            raise ValueError('Invalid Rogue result status.')
        return ('start_failed' if record.get('reason') == 'process_start_failed' else 'unconfirmed'), None
    selection = attempt['selection']
    expected, result = record.get('expected'), record.get('result')
    if not isinstance(expected, dict) or not isinstance(result, dict):
        raise ValueError('Rogue result configuration is missing.')
    for key in ('car', 'track', 'layout', 'skin'):
        if expected.get(key, '') != selection.get(key, ''):
            raise ValueError('Rogue result configuration differs from the challenge.')
    if (not isinstance(expected.get('cars'), list) or len(expected['cars']) != selection['opponents'] + 1
            or expected['cars'][0] != selection['car']):
        raise ValueError('Rogue result grid differs from the challenge.')
    if expected.get('sessions') != [dict(type=3, target_laps=selection['laps'])]:
        raise ValueError('Rogue result laps differ from the challenge.')
    if any(result.get(key, '') != selection.get(key, '') for key in ('car', 'track', 'layout')):
        raise ValueError('Rogue result identity differs from the challenge.')
    sessions = result.get('sessions')
    if not isinstance(sessions, list) or len(sessions) != 1 or not isinstance(sessions[0], dict):
        raise ValueError('Rogue result race is missing.')
    row = sessions[0]
    if (type(row.get('type')) is not int or row['type'] != 3
            or type(row.get('target_laps')) is not int or row['target_laps'] != selection['laps']):
        raise ValueError('Rogue result race differs from the challenge.')
    # Only an explicit cancellation is evidence for a failed, unfinished race.
    if row.get('race_completed') is False and row.get('completion_evidence') == 'explicit_cancelled':
        return 'lost', None
    if row.get('race_completed') is not True:
        return 'unconfirmed', None
    witnessed = (row.get('completion_evidence') == 'csp_player_finished'
                 and results.captured_finish(record, row))
    if not witnessed and (row.get('completion_evidence') != 'player_lap_target_reached'
            or type(row.get('completed_laps')) is not int or row['completed_laps'] < selection['laps']):
        return 'unconfirmed', None
    if row.get('position') is None:
        return 'unconfirmed', None
    position = _integer(row.get('position'), 1, selection['opponents'] + 1)
    return ('won' if position <= attempt['target_position'] else 'lost'), position


def _outcome_reason(status, record):
    reason = record.get('reason', '')
    if status == 'unconfirmed' and record.get('status') == 'imported':
        row = record['result']['sessions'][0]
        if row.get('race_completed') is not True:
            return 'finish_not_confirmed'
        if (row.get('completion_evidence') not in ('player_lap_target_reached', 'csp_player_finished')
                or type(row.get('completed_laps')) is not int
                or row['completed_laps'] < row['target_laps']):
            return 'finish_evidence_missing'
        if row.get('position') is None:
            return 'final_position_missing'
    return reason


class Store:
    def __init__(self, path):
        self.path = safe.absolute(path)
        self.reload()

    def reload(self):
        self.state = load(self.path)
        return deepcopy(self.state)

    def _change(self, callback):
        with _locked(self.path):
            state = load(self.path)
            _archive_directory(self.path, state['profile'])
            result = callback(state)
            clean(state)
            _compact(self.path, state)
            _save(self.path, state)
            self.state = state
            return deepcopy(result)

    def start_run(self, base, mode='deterministic', seed=None):
        if not isinstance(base, dict) or mode not in ('deterministic', 'ai'):
            raise ValueError('Invalid Rogue run settings.')
        seed = secrets.randbits(64) if seed is None else _integer(seed, 0, 2**64 - 1)
        def change(state):
            if state['run'] is not None and state['run']['status'] == 'active':
                raise ValueError('Reset the current Rogue run before starting another.')
            state['run'] = dict(id=uuid.uuid4().hex, seed=seed, mode=mode, base=deepcopy(base),
                                wins=0, streak=0, lives=1, status='active', challenge=None,
                                attempts={}, pending_attempt=None, rewarded_badges=[], history=[],
                                last_challenge=None, last_outcome=None, created_utc=_now())
            return state['run']
        return self._change(change)

    def reset_run(self):
        def change(state):
            state['run'] = None
            return state
        return self._change(change)

    def reset_profile(self):
        """Após confirmação da UI, preserva os bytes e zera somente o Rogue.

        Não recupera arquivo inválido nem busca resultados antigos. Retorna o
        estado novo; erro de cópia/gravação mantém self.state e o perfil anterior.
        """
        with _locked(self.path):
            try:
                raw, signature = _profile_snapshot(self.path)
            except FileNotFoundError:
                # Perfil nunca criado: nada a copiar ou substituir.
                state = clean()
                self.state = state
                return deepcopy(state)
            clean(results._json(raw))  # valida o conteúdo atual, não a cópia em memória
            _backup_profile(self.path, raw)
            current, current_signature = _profile_snapshot(self.path)
            if current != raw or current_signature != signature:
                raise RuntimeError('Rogue profile changed during reset. Original file kept.')
            state = clean()
            _save(self.path, state)
            self.state = state
            return deepcopy(state)

    def set_challenge(self, proposal):
        proposal = deepcopy(proposal)
        def change(state):
            run = _active(state)
            _challenge(proposal, stage(run))
            if run['challenge'] is not None:
                if run['challenge'] == proposal:
                    return run['challenge']
                raise ValueError('Finish or reset the current Rogue challenge first.')
            if run['pending_attempt'] is not None:
                raise ValueError('Finish the current Rogue attempt first.')
            if any(row['challenge_id'] == proposal['challenge_id'] for row in run['attempts'].values()):
                raise ValueError('This Rogue challenge was already used.')
            run['challenge'] = proposal
            run['challenge_xp'] = 0
            return proposal
        return self._change(change)

    def begin_attempt(self, selection, *, session_id=None):
        selection = deepcopy(selection)
        def change(state):
            run = _active(state)
            challenge = run['challenge']
            if challenge is None or not session_settings.same(selection, challenge['selection']):
                raise ValueError('Rogue race differs from the locked challenge.')
            identity = uuid.uuid4().hex
            session = _identity(session_id) if session_id is not None else identity
            if (session in state['profile']['processed_sessions']
                    or any(a['session_id'] == session for a in run['attempts'].values())
                    or _archived(self.path, state['profile'], session) is not None):
                raise ValueError('This Rogue session was already used.')
            # An interrupted launcher must be resumable after a machine restart.
            # It provides no evidence for a sporting defeat or a reward.
            pending = run['pending_attempt']
            if pending is not None:
                previous = run['attempts'][pending]
                previous['status'] = 'finished'
                previous['outcome'] = _summary(run, 'unconfirmed', attempt=previous, reason='attempt_interrupted')
                state['profile']['processed_sessions'][previous['session_id']] = previous['outcome']
            attempt = dict(id=identity, run_id=run['id'], challenge_id=challenge['challenge_id'],
                           session_id=session, selection=deepcopy(challenge['selection']),
                           target_position=challenge['target_position'], status='pending', started_utc=_now())
            run['attempts'][identity] = attempt
            run['pending_attempt'] = identity
            return attempt
        return self._change(change)

    def finish_attempt(self, attempt_id, record):
        def change(state):
            run = state['run']
            if run is None or attempt_id not in run['attempts']:
                if run is not None and isinstance(record, dict):
                    archived = _archived(self.path, state['profile'], record.get('session_id'))
                    attempt = archived.get('attempt') if archived else None
                    if attempt and attempt['id'] == attempt_id and attempt['run_id'] == run['id']:
                        return archived['receipt']
                raise ValueError('Unknown Rogue attempt. Progress kept.')
            attempt = run['attempts'][attempt_id]
            if attempt['status'] == 'finished':
                return attempt['outcome']
            if run['pending_attempt'] != attempt_id or run['status'] != 'active':
                raise ValueError('Rogue attempt is not active.')
            challenge = run['challenge']
            if challenge is None or challenge['challenge_id'] != attempt['challenge_id']:
                raise ValueError('Rogue attempt challenge differs.')
            status, position = _outcome(attempt, record)
            profile, xp, new_badges = state['profile'], 0, []
            if status in ('won', 'lost'):
                target_xp = XP_PER_CHALLENGE if status == 'won' else PARTIAL_XP if position is not None else 0
                xp = max(0, target_xp - run.get('challenge_xp', 0))
                run['challenge_xp'] = max(run.get('challenge_xp', 0), target_xp)
                selection = attempt['selection']
                for key, identity in (('car_xp', selection['car']), ('track_xp', _track_key(selection))):
                    profile[key][identity] = profile[key].get(identity, 0) + xp
                if status == 'won':
                    run['wins'] += 1
                    run['streak'] += 1
                    profile['best_wins'] = max(profile['best_wins'], run['wins'])
                    identity = _track_key(selection)
                    profile['track_wins'][identity] = profile['track_wins'].get(identity, 0) + 1
                    for identity, threshold, _, _ in _BADGES:
                        if run['streak'] >= threshold and identity not in run['rewarded_badges']:
                            run['rewarded_badges'].append(identity)
                            run['lives'] = min(MAX_LIVES, run['lives'] + 1)
                            if identity not in profile['badges']:
                                profile['badges'].append(identity)
                                new_badges.append(identity)
                    run['last_challenge'] = deepcopy(challenge)
                    run['challenge'] = None
                    run['stage'] = challenge['stage'] + 1
                else:
                    run['streak'] = 0
                    if run['lives'] > 0:
                        run['lives'] -= 1
                        if position is not None:
                            run['last_challenge'] = deepcopy(challenge)
                            run['challenge'] = None
                            run['stage'] = challenge['stage'] + 1
                    else:
                        run['status'] = 'ended'
                run['history'].append(dict(car=selection['car'], track=selection['track'],
                    layout=selection.get('layout', ''), class_id=challenge.get('class_id'), position=position,
                    target_position=attempt['target_position'], won=status == 'won', stage=challenge['stage'],
                    challenge_id=challenge['challenge_id']))
                run['history'] = run['history'][-100:]
            new_stickers = rogue_rewards.newly_unlocked(profile, owned=profile['stickers'])
            profile['stickers'].extend(new_stickers)
            outcome = _summary(run, status, attempt=attempt, position=position, xp=xp,
                               badges=new_badges, stickers=new_stickers, reason=_outcome_reason(status, record))
            outcome['stage'] = challenge['stage']
            attempt.update(status='finished', outcome=outcome, ended_utc=_now(),
                           result_sha256=hashlib.sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest())
            run['pending_attempt'] = None
            run['last_outcome'] = outcome
            profile['processed_sessions'][attempt['session_id']] = outcome
            return outcome
        return self._change(change)
