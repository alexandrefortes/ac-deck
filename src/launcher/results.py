"""Resultados locais por tentativa; não infere sucesso pelo código de saída."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from . import file_io as safe
from . import content

LIMIT = 8*1024*1024


class InvalidResult(ValueError):
    pass


def _integer(value, low=0, high=100000):
    if type(value) is not int or not low <= value <= high:
        raise InvalidResult('invalid_number')
    return value


def _lap_time(value):
    value = _integer(value, -1, 4294967295)
    # Missing timing must not invalidate independent lap totals/classification.
    return None if value in (-1, 0, 2147483647, 4294967295) else value


def captured_finish(record, row):
    capture, config = record.get('finish_capture'), record.get('expected')
    if not isinstance(capture, dict) or not isinstance(config, dict):
        return False
    return (type(capture.get('schema_version')) is int and capture['schema_version'] == 1
            and capture.get('session_id') == record.get('session_id') and capture.get('finished') is True
            and type(capture.get('position')) is int and capture['position'] == row.get('position')
            and type(capture.get('completed_laps')) is int and capture['completed_laps'] == row.get('completed_laps')
            and all(capture.get(key) == config.get(key) for key in ('car', 'track', 'layout', 'skin', 'cars'))
            and capture.get('target_laps') == row.get('target_laps')
            and capture.get('config_sha256') == hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest())


def _read(path):
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size > LIMIT:
            raise InvalidResult('too_large')
        raw = stream.read(LIMIT+1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    if (len(raw) > LIMIT or safe.signature(before) != safe.signature(after)
            or safe.signature(after) != safe.signature(current)):
        raise InvalidResult('source_changed_while_reading')
    return raw, dict(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw), mtime_ns=after.st_mtime_ns)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InvalidResult('duplicate_json_key')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(InvalidResult('invalid_number')))
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidResult('invalid_json') from None


def _write(path, data, *, replace=False):
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
        if not replace:
            raise FileExistsError('Result already preserved')
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    descriptor = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0), 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
        safe.check_components(path)
        if path.exists():
            safe.require_reference(path.lstat(), path)
            if not replace:
                raise FileExistsError('Result already preserved')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _save(path, data, *, replace=False):
    _write(path, (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode(), replace=replace)


def expected(history):
    """O INI efetivamente escrito prevalece sobre seleções de eventos instalados."""
    race = content.read_ini(history/'race.ini')
    count = _integer(int(race['RACE']['CARS']), 1, 48)
    model = race['RACE']['MODEL']
    cars = [race['CAR_'+str(i)].get('MODEL','-') for i in range(count)]
    cars = [model if value=='-' else value for value in cars]
    sessions = []
    for i in range(32):
        section = 'SESSION_'+str(i)
        if section not in race:
            break
        value = race[section]
        sessions.append(dict(type=int(value['TYPE']), target_laps=int(value.get('LAPS','0'))))
    if not sessions:
        raise InvalidResult('missing_session_configuration')
    return dict(track=race['RACE']['TRACK'], layout=race['RACE'].get('CONFIG_TRACK',''),
                car=cars[0], skin=race['CAR_0'].get('SKIN',''), cars=cars, sessions=sessions)


def parse(data, config):
    if not isinstance(data, dict) or not isinstance(data.get('players'), list) or not isinstance(data.get('sessions'), list):
        raise InvalidResult('invalid_structure')
    reported_track = data.get('track')
    # Native results can join the configured track and layout with a hyphen.
    # Compare the whole configured pair; never split or accept an ID prefix.
    layout_reported = (bool(config['layout']) and isinstance(reported_track, str)
                       and reported_track.casefold()==(config['track']+'-'+config['layout']).casefold())
    if (not isinstance(reported_track, str)
            or (reported_track.casefold()!=config['track'].casefold() and not layout_reported)):
        raise InvalidResult('track_mismatch')
    players, sessions = data['players'], data['sessions']
    if not players or len(players)!=len(config['cars']):
        raise InvalidResult('grid_mismatch')
    for player, car in zip(players,config['cars']):
        if not isinstance(player,dict) or not isinstance(player.get('car'),str) or player['car'].casefold()!=car.casefold():
            raise InvalidResult('car_mismatch')
    if players[0].get('skin','').casefold()!=config['skin'].casefold():
        raise InvalidResult('skin_mismatch')
    if _integer(data.get('number_of_sessions'),1,32)!=len(sessions) or len(sessions)!=len(config['sessions']):
        raise InvalidResult('session_count_mismatch')
    # Base-only legacy results still do not independently identify the layout.
    extras = data.get('extras') or []
    if not isinstance(extras,list):
        raise InvalidResult('invalid_extras')
    cancelled = any(isinstance(item,dict) and item.get('name')=='__custom_mode'
                    and item.get('cancelled') is True for item in extras)
    rows = []
    for native, wanted in zip(sessions,config['sessions']):
        if not isinstance(native,dict) or _integer(native.get('type'),0,20)!=wanted['type']:
            raise InvalidResult('session_type_mismatch')
        kind = wanted['type']
        target = _integer(native.get('lapsCount',0))
        if kind==3 and target!=wanted['target_laps']:
            raise InvalidResult('lap_target_mismatch')
        totals = native.get('lapstotal')
        if totals is not None:
            if not isinstance(totals,list) or len(totals)!=len(players):
                raise InvalidResult('invalid_lap_totals')
            totals = [_integer(n) for n in totals]
        laps = []
        for lap in native.get('laps') or []:
            if not isinstance(lap,dict):
                raise InvalidResult('invalid_lap')
            car = _integer(lap.get('car'),0,len(players)-1)
            if car==0:
                laps.append(dict(lap=_integer(lap.get('lap')), time_ms=_lap_time(lap.get('time')),
                                 cuts=_integer(lap.get('cuts')) if lap.get('cuts') is not None else None))
        best = []
        for lap in native.get('bestLaps') or []:
            if not isinstance(lap,dict):
                raise InvalidResult('invalid_best_lap')
            car = _integer(lap.get('car'),0,len(players)-1)
            value = _lap_time(lap.get('time'))
            if car==0 and value is not None and value<86400000:
                best.append(value)
        position = None
        order = native.get('raceResult')
        if kind==3 and isinstance(order,list) and len(order)==len(players):
            if all(type(n) is int for n in order) and sorted(order)==list(range(len(players))):
                position = order.index(0)+1
        completed = False if cancelled else (True if kind==3 and target>0 and totals is not None and totals[0]>=target else None)
        rows.append(dict(type=kind, target_laps=target, completed_laps=totals[0] if totals is not None else None,
                         best_lap_ms=min(best) if best else None, position=position,
                         race_completed=completed, won=(position==1 if completed and position is not None else None),
                         completion_evidence='explicit_cancelled' if cancelled else
                             'player_lap_target_reached' if completed else 'not_confirmed',
                         recorded_laps=laps))
    return dict(track=config['track'], layout=config['layout'],
                layout_evidence=('track_layout_reported_by_result' if layout_reported
                                 else 'configured_not_reported_by_result'),
                car=config['car'], sessions=rows)


class Collector:
    def __init__(self, cfg, history):
        self.history = safe.source_root(history)
        from . import ai_usage
        self.usage_path=self.history.parents[1]/'ai-usage.json'
        try:ai_usage.load(self.usage_path)
        except (OSError,ValueError,RuntimeError):pass
        self.source = safe.absolute(cfg).parent/'out/race_out.json'
        self.config = expected(self.history)
        self.baseline = None
        self.baseline_error = None
        try:
            _, self.baseline = _read(self.source)
        except FileNotFoundError:
            pass
        except (OSError,ValueError,RuntimeError):
            self.baseline_error = 'baseline_unreadable'
        self.started_ns = time.time_ns()
        self.closed = False
        self.finish_capture = None
        self.record = dict(schema_version=1, session_id=self.history.name, status='pending',
                           reason='session_not_collected', started_ns=self.started_ns, expected=self.config,
                           baseline=self.baseline, baseline_error=self.baseline_error)
        _save(self.history/'result.json',self.record)

    def enable_finish_capture(self, game):
        from .finish_capture import Capture
        if len(self.config['sessions']) == 1 and self.config['sessions'][0]['type'] == 3:
            self.finish_capture = Capture(game, self.history, self.config)

    def finish(self, exit_code, *, start_failed=False):
        if self.closed:
            return self.record
        self.closed = True
        self.record.update(ended_ns=time.time_ns(), collected_utc=datetime.now(timezone.utc).isoformat(),
                           process_exit_code=exit_code, status='unavailable')
        try:
            if start_failed:
                raise InvalidResult('process_start_failed')
            if self.baseline_error:
                raise InvalidResult(self.baseline_error)
            raw, fingerprint = _read(self.source)
            self.record['source'] = fingerprint
            if not self.started_ns<=fingerprint['mtime_ns']<=self.record['ended_ns']:
                raise InvalidResult('not_written_during_session')
            if self.baseline and self.baseline['sha256']==fingerprint['sha256']:
                raise InvalidResult('unchanged_result')
            _write(self.history/'result-source.json',raw)
            summary = parse(_json(raw),self.config)
            self.record.update(status='imported', reason='fresh_file_and_matching_configuration', result=summary)
        except FileNotFoundError:
            self.record['reason'] = 'result_missing'
        except InvalidResult as error:
            self.record['reason'] = str(error)
        except (OSError,ValueError,RuntimeError,AttributeError,TypeError):
            self.record['reason'] = 'result_unreadable_or_unsupported'
        if self.finish_capture is not None and not start_failed:
            try:
                evidence = self.finish_capture.read(self.started_ns, self.record['ended_ns'])
                result = self.record.get('result')
                if result is None and self.record['reason'] in ('result_missing', 'unchanged_result', 'not_written_during_session'):
                    result = dict(car=self.config['car'], track=self.config['track'], layout=self.config['layout'],
                                  layout_evidence='csp_track_layout', sessions=[dict(type=3,
                                  target_laps=self.config['sessions'][0]['target_laps'], best_lap_ms=None, recorded_laps=[])])
                row = result['sessions'][0] if result else None
                if (row is not None and row.get('completion_evidence') != 'explicit_cancelled'
                        and (row.get('race_completed') is not True or row.get('position') is None)):
                    row.update(race_completed=True, completion_evidence='csp_player_finished',
                               completed_laps=evidence['completed_laps'], position=evidence['position'],
                               won=evidence['position'] == 1)
                    self.record.update(native_reason=self.record['reason'], finish_capture=evidence,
                                       result=result, status='imported', reason='csp_confirmed_finish')
            except (OSError, ValueError, RuntimeError):
                pass  # No witness never fabricates a finish or a classification.
        if self.finish_capture is not None:
            try:self.finish_capture.close()
            except (OSError, ValueError, RuntimeError):pass
        _save(self.history/'result.json',self.record,replace=True)
        from . import ai_usage
        try:ai_usage.record(self.usage_path,self.record)
        except (OSError,ValueError,RuntimeError):
            self.record['ai_usage_saved']=False
        return self.record


def message(record):
    if record['status']!='imported':
        return 'Session ended. Result unavailable ('+record['reason']+').'
    row = record['result']['sessions'][-1]
    parts = ['Result saved']
    if row['position'] is not None:
        parts.append('P'+str(row['position'])+(' (finish unconfirmed)' if row['race_completed'] is not True else ''))
    if row['completed_laps'] is not None:
        parts.append(str(row['completed_laps'])+' laps')
    if row['best_lap_ms'] is not None:
        minutes, remain = divmod(row['best_lap_ms'],60000)
        parts.append(f'best {minutes}:{remain//1000:02}.{remain%1000:03}')
    return ' / '.join(parts)+'.'


def history(package, limit=50):
    _integer(limit,1,1000)
    root = safe.source_root(package)/'launcher/sessions'
    safe.check_components(root)
    rows = []
    if root.is_dir():
        for folder in sorted(root.iterdir(),reverse=True):
            safe.check_components(folder)
            path = folder/'result.json'
            if not folder.is_dir() or not path.exists():
                continue
            try:
                data = _json(_read(path)[0])
                if data.get('schema_version')!=1 or data.get('session_id')!=folder.name:
                    continue
                if data.get('status') not in ('pending','unavailable','imported'):
                    continue
                if data['status']=='imported' and (not isinstance(data.get('result'),dict)
                        or not isinstance(data['result'].get('sessions'),list)):
                    continue
                row = {key:data.get(key) for key in ('session_id','status','reason','started_ns','ended_ns','result')}
                rows.append(row)
            except (OSError,ValueError,RuntimeError,AttributeError,TypeError):
                continue
            if len(rows)>=limit:
                break
    imported = [r for r in rows if r['status']=='imported' and isinstance(r['result'],dict)]
    sessions = [s for row in imported for s in row['result'].get('sessions',[]) if isinstance(s,dict)]
    bests = {}
    for row in imported:
        result = row['result']
        times = [s.get('best_lap_ms') for s in result.get('sessions',[]) if isinstance(s,dict)]
        times = [n for n in times if type(n) is int and 0<n<86400000]
        if times:
            key = tuple(result.get(k) for k in ('car','track','layout'))
            if all(isinstance(k,str) for k in key):
                bests[key] = min([bests[key],*times]) if key in bests else min(times)
    return dict(schema_version=1, entries=rows, totals=dict(attempts=len(rows), imported=len(imported),
        unavailable=sum(r['status']=='unavailable' for r in rows), pending=sum(r['status']=='pending' for r in rows),
        completed_races=sum(s.get('type')==3 and s.get('race_completed') is True for s in sessions),
        wins=sum(s.get('won') is True for s in sessions)),
        best_laps=[dict(car=key[0],track=key[1],layout=key[2],time_ms=value) for key,value in sorted(bests.items())],
        notes='Only this listed window is summarized. Best laps span conditions, not skill scores. '
              'Lapped or timed finishes may remain unconfirmed. Older sessions without result.json are not imported.')
