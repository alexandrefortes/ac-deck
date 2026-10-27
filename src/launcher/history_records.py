"""Histórico compartilhado: lê tentativas locais, sem importar resultados antigos.

Uma tentativa sem result.json permanece visível como resultado indisponível.
Somente session.json e result.json são lidos; nada é escrito ou executado.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import re

from . import file_io, results, session_settings


LIMIT = 256 * 1024
_ERRORS = (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError)


def read_record(path):
    """Lê um objeto JSON estável e limitado; devolve objeto e mtime em ns."""
    stream, before = file_io.open_reference(path)
    with stream:
        if before.st_size > LIMIT:
            raise ValueError('History record too large')
        raw = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
    file_io.check_components(path)
    current = path.lstat()
    file_io.require_reference(after, path)
    file_io.require_reference(current, path)
    if (len(raw) > LIMIT or file_io.signature(before) != file_io.signature(after)
            or file_io.signature(after) != file_io.signature(current)):
        raise ValueError('History record changed while reading')
    data = results._json(raw)
    if not isinstance(data, dict):
        raise ValueError('Invalid history record')
    return data, after.st_mtime_ns


def _number(value, low=0, high=100000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid history number')
    return value


def _selection(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid history selection')
    for key in ('car', 'track', 'layout'):
        text = value.get(key)
        if not isinstance(text, str) or len(text) > 256 or ('\x00' in text):
            raise ValueError('Invalid history content')
        if key != 'layout' and not text:
            raise ValueError('Missing history content')
    if 'event_synthetizer' in value:
        raise ValueError('Nested history proposal')
    return value


def _proposal(value, selected):
    if value is None:
        return None
    if (not isinstance(value, dict) or type(value.get('schema_version')) is not int
            or value['schema_version'] not in (1, 2)
            or not isinstance(value.get('base'), dict)
            or not all(isinstance(value.get(key), str)
                       for key in ('class_id', 'class_name', 'car_name', 'track_name'))
            or not session_settings.same(_selection(value.get('selection')), selected)):
        raise ValueError('Invalid history proposal')
    # A validação contra o catálogo atual continua obrigatória ao restaurar.
    return value


def _timestamp(session_id, fallback):
    match = re.fullmatch(r'(\d{8}T\d{6}Z)-[A-Za-z0-9_-]+', session_id)
    if match:
        try:
            date = datetime.strptime(match[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            return int(date.timestamp()) * 1000000000
        except ValueError:
            pass
    return fallback


def validate_result(data, session_id, selected):
    """Valida identidade/conclusão do resultado e devolve seu resumo histórico."""
    if (type(data.get('schema_version')) is not int or data['schema_version'] != 1
            or data.get('session_id') != session_id
            or data.get('status') not in ('pending', 'unavailable', 'imported')):
        raise ValueError('Invalid result record')
    start = _number(data.get('started_ns'), 1, 2**63 - 1)
    end = data.get('ended_ns')
    if end is not None:
        _number(end, start, 2**63 - 1)
    status = data['status']
    reason = data.get('reason')
    reason = reason if isinstance(reason, str) and re.fullmatch('[a-z_]{1,80}', reason) else None
    row = dict(status=status, reason=reason, started_ns=start, ended_ns=end,
               completion='unavailable', result=None)
    if status != 'imported':
        row['summary'] = ('Result not collected; completion unconfirmed.' if status == 'pending'
                          else 'Result unavailable for this attempt.')
        return row
    config, result = data.get('expected'), data.get('result')
    if (not isinstance(config, dict) or not isinstance(result, dict)
            or not isinstance(config.get('cars'), list) or not config['cars']
            or len(config['cars']) > 48
            or not isinstance(config.get('sessions'), list)
            or not isinstance(result.get('sessions'), list)
            or not 1 <= len(result['sessions']) <= 32
            or len(result['sessions']) != len(config['sessions'])):
        raise ValueError('Invalid imported result')
    if not all(isinstance(car, str) and car for car in config['cars']):
        raise ValueError('Invalid result grid')
    for key in ('car', 'track', 'layout'):
        if not isinstance(result.get(key), str) or result[key] != config.get(key):
            raise ValueError('Result identity mismatch')
        # Eventos instalados podem substituir a seleção pelo race.ini efetivo.
        if not selected.get('event') and result[key] != selected[key]:
            raise ValueError('Result differs from selection')
    summary = []
    compact = []
    for recorded, wanted in zip(result['sessions'], config['sessions']):
        if not isinstance(recorded, dict) or not isinstance(wanted, dict):
            raise ValueError('Invalid result session')
        kind = _number(recorded.get('type'), 0, 20)
        target = _number(recorded.get('target_laps'))
        if kind != wanted.get('type') or target != wanted.get('target_laps'):
            raise ValueError('Result session mismatch')
        laps, best, position = (recorded.get(key) for key in ('completed_laps', 'best_lap_ms', 'position'))
        if laps is not None:
            _number(laps)
        if best is not None:
            _number(best, 1, 86399999)
        if position is not None:
            _number(position, 1, len(config['cars']))
            if kind != 3:
                raise ValueError('Position outside a race')
        completed, evidence = recorded.get('race_completed'), recorded.get('completion_evidence')
        if completed is True:
            witnessed = (evidence == 'csp_player_finished'
                         and results.captured_finish(data, recorded))
            if (kind != 3 or target < 1 or laps is None or
                    not witnessed and (laps < target or evidence != 'player_lap_target_reached')):
                raise ValueError('Unproven result completion')
            completion, label = 'confirmed', 'Finished'
        elif completed is False:
            if evidence != 'explicit_cancelled':
                raise ValueError('Unproven cancellation')
            completion, label = 'cancelled', 'Cancelled'
        elif completed is None and evidence == 'not_confirmed':
            completion, label = 'unconfirmed', 'Finish unconfirmed'
        else:
            raise ValueError('Invalid result completion')
        summary = [label]
        if position is not None:
            summary.append('P' + str(position))
        if laps is not None:
            summary.append(str(laps) + ' laps')
        if best is not None:
            minutes, rest = divmod(best, 60000)
            summary.append(f'best {minutes}:{rest//1000:02}.{rest%1000:03}')
        compact.append(dict(type=kind, target_laps=target, completed_laps=laps,
                            best_lap_ms=best, position=position, race_completed=completed,
                            completion_evidence=evidence))
    row.update(summary=' / '.join(summary) + '.', completion=completion,
               result={**{key: result[key] for key in ('car', 'track', 'layout')}, 'sessions': compact})
    return row


def load(synthesis_store, limit=50):
    """Retorna tentativas recentes; não valida disponibilidade atual do conteúdo.

    ``started_ns`` só é preenchido por result.json válido. ``timestamp_ns`` usa
    o início registrado, o ID UTC da tentativa ou, por último, o mtime do JSON.
    Um resultado ausente/inválido nunca fornece métricas nem conclusão.
    """
    _number(limit, 1, 1000)
    if synthesis_store is None:
        return []
    try:
        root = file_io.absolute(Path(synthesis_store).parent / 'sessions')
        file_io.check_components(root)
        if not root.is_dir():
            return []
        folders = list(root.iterdir())
    except _ERRORS:
        return []
    rows = []
    for folder in folders:
        try:
            file_io.check_components(folder)
            if not folder.is_dir():
                continue
            session, modified = read_record(folder / 'session.json')
            selected = _selection(session.get('selection'))
            proposal = _proposal(session.get('event_synthetizer'), selected)
            row = dict(id=folder.name, selection=selected, proposal=proposal,
                       summary='Result unavailable (not collected for this attempt).',
                       status='unavailable', reason='not_collected', started_ns=None,
                       ended_ns=None, completion='unavailable', result=None,
                       timestamp_ns=_timestamp(folder.name, modified))
            try:
                data, _ = read_record(folder / 'result.json')
                row.update(validate_result(data, folder.name, selected))
                row['timestamp_ns'] = row['started_ns']
            except FileNotFoundError:
                pass
            except _ERRORS:
                row.update(summary='Result unavailable (invalid or unreadable record).', reason='invalid_result')
            rows.append(row)
        except _ERRORS:
            continue
    rows.sort(key=lambda row: (row['timestamp_ns'], row['id']), reverse=True)
    return rows[:limit]
