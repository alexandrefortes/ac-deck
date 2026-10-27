"""Campanhas nativas: catálogo, progresso e atualização delimitada por sessão.

O launcher original persiste career.ini; acs.exe fornece apenas race_out.json.
Não há importação retrospectiva de resultados, reset ou gravação ao navegar.
"""
import configparser
import hashlib
import re
from pathlib import Path

from . import file_io as safe
from . import content, results

EVENT = re.compile(r'event([1-9][0-9]*)\Z', re.I)
MEDALS = {1: 'Bronze', 2: 'Silver', 3: 'Gold'}


def natural(value):
    return tuple(int(x) if x.isdigit() else x.casefold() for x in re.split(r'(\d+)', value))


def _number(value, default=0):
    try:
        number = int(value)
        return number if 0 <= number <= 2147483647 else default
    except (TypeError, ValueError):
        return default


def series_info(path):
    ini = content.read_ini(path)
    raw = ini.get('SERIES', 'POINTS', fallback='0').split(',')
    points = [_number(x.strip()) for x in raw]
    return dict(id=path.parent.name, name=content.label(ini.get('SERIES', 'NAME', fallback=''), path.parent.name),
        code=content.label(ini.get('SERIES', 'CODE', fallback=''), ''),
        description=content.label(ini.get('SERIES', 'DESCRIPTION', fallback=''), ''),
        championship=any(points), points=points,
        requires=[x.strip().casefold() for x in ini.get('SERIES', 'REQUIRES', fallback='').split(',') if x.strip()],
        requires_any=ini.get('SERIES', 'REQUIRESANY', fallback='0') == '1',
        goals={key: _number(ini.get('GOALS', key.upper(), fallback='0'))
               for key in ('points', 'ranking', 'tier1', 'tier2', 'tier3')})


def event_metadata(path, ini):
    career = path.parent.parent.parent.name == 'career'
    series = series_info(path.parent.parent/'series.ini') if career else None
    match = EVENT.fullmatch(path.parent.name) if career else None
    return dict(kind='career' if career else 'special',
        group_id='career:'+series['id'] if series else 'special',
        series=series, event_number=int(match[1])-1 if match else None,
        description=content.label(ini.get('EVENT', 'DESCRIPTION', fallback=''), ''),
        session_types=[_number(ini[s].get('TYPE')) for s in ini.sections() if re.fullmatch(r'SESSION_\d+', s)],
        conditions=[dict(type=(ini[s].get('TYPE') or ini.get('CONDITION_0','TYPE',fallback='')).upper(), objective=_number(ini[s].get('OBJECTIVE'), -1))
                    for s in ('CONDITION_0', 'CONDITION_1', 'CONDITION_2') if s in ini])


def progress_path(cfg):
    return safe.absolute(cfg).parent/'launcherdata/filestore/career.ini'


def _decode(raw):
    try:
        return raw.decode('utf-8-sig'), 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
    except UnicodeError:
        return raw.decode('cp1252'), 'cp1252'


def _parse(raw):
    text, encoding = _decode(raw)
    ini = configparser.ConfigParser(interpolation=None, strict=True, inline_comment_prefixes=(';',))
    ini.optionxform = str.upper
    try:ini.read_string(text)
    except configparser.Error as error:raise ValueError('Invalid native career progress') from error
    names = [name.casefold() for name in ini.sections()]
    if len(set(names)) != len(names):
        raise ValueError('Ambiguous native career sections')
    return ini, text, encoding


def load(cfg):
    if cfg is None:
        return dict(status='unavailable', sections={}, complete=set(), error='Progress path unavailable')
    path = progress_path(cfg)
    try:
        raw, fingerprint = results._read(path)
        ini, _, _ = _parse(raw)
        sections = {section.casefold(): dict(ini[section]) for section in ini.sections()}
        completed = {x.strip().casefold() for x in sections.get('career', {}).get('COMPLETE', '').split(',') if x.strip()}
        return dict(status='loaded', sections=sections, complete=completed, fingerprint=fingerprint)
    except FileNotFoundError:
        return dict(status='missing', sections={}, complete=set())
    except (OSError, ValueError, RuntimeError):
        return dict(status='unavailable', sections={}, complete=set(), error='Native career progress unavailable; original file kept')


def groups(catalog, progress):
    found = {}
    for event in catalog.get('events', []):
        identity = event.get('group_id', event.get('group', 'Events'))
        if identity not in found:
            series = event.get('series')
            found[identity] = dict(id=identity, name=event.get('group', 'Events'), series=series, events=[])
        found[identity]['events'].append(event)
    values = list(found.values())
    for group in values:
        group['events'].sort(key=lambda event: natural(event['id']))
        series = group['series']
        group['completed'] = bool(series and series['id'].casefold() in progress['complete'])
        needed = series.get('requires', []) if series else []
        satisfied = [key in progress['complete'] for key in needed]
        group['locked'] = bool(needed and not (any(satisfied) if series.get('requires_any') else all(satisfied)))
        group['completed_events'] = sum(event_status(event, progress)['completed'] for event in group['events'])
    return sorted(values, key=lambda group: (group['series'] is None, natural(group['series']['id'] if group['series'] else group['name'])))


def event_status(event, progress):
    series = event.get('series')
    if not series:
        return dict(completed=False, label='Special event / achievement progress unavailable', value=None)
    if progress['status'] == 'unavailable':
        return dict(completed=False, label='Progress unavailable', value=None)
    index = event.get('event_number')
    if index is None:
        return dict(completed=False, label='Unsupported event numbering', value=None)
    value = _number(progress['sections'].get(series['id'].casefold(), {}).get('EVENT'+str(index)))
    if series['championship']:
        return dict(completed=value > 0, label='Completed / P'+str(value) if value else 'Not completed', value=value)
    return dict(completed=value in MEDALS, label='Completed / '+MEDALS[value] if value in MEDALS else 'No medal yet', value=value)


def playable(event, progress, catalog):
    if not any(c['id']==event['car'] for c in catalog['cars']) or not any(
            (t['id'],t.get('layout',''))==(event['track'],event.get('layout','')) for t in catalog['tracks']):
        return 'Required car or track is not installed'
    if event.get('available') is False:
        return event.get('unavailable_reason', 'Required content is not installed')
    series = event.get('series')
    if not series:
        return None
    group = next((g for g in groups(catalog, progress) if g['id'] == event['group_id']), None)
    if group and group['locked']:
        return 'Complete the required series first: '+', '.join(series['requires'])
    if series['championship']:
        remaining = [e for e in group['events'] if not event_status(e, progress)['completed']]
        if remaining and event['id'] != remaining[0]['id'] and not event_status(event, progress)['completed']:
            return 'Complete the previous championship round first'
    return None


def _patch(raw, changes):
    """Altera só as chaves declaradas, preservando comentários e campos alheios."""
    _, text, encoding = _parse(raw)
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines(keepends=True)
    for section, updates in changes.items():
        start = next((i for i, line in enumerate(lines) if re.match(r'\s*\['+re.escape(section)+r'\]', line, re.I)), None)
        if start is None:
            if lines and not lines[-1].endswith(('\r', '\n')):lines[-1] += newline
            lines += [newline+'['+section.upper()+']'+newline]
            start = len(lines)-1
        end = next((i for i in range(start+1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
        for key, value in updates.items():
            match = next((i for i in range(start+1, end) if re.match(r'\s*'+re.escape(key)+r'\s*[:=]', lines[i], re.I)), None)
            replacement = key.upper()+'='+str(value)+newline
            if match is None:
                lines.insert(end, replacement)
                end += 1
            else:
                lines[match] = replacement
    return ''.join(lines).encode(encoding)


def _achieved(event, native, summary):
    """Somente tipos/regras observados no launcher nativo; positivo não é exit code."""
    if any(isinstance(x, dict) and x.get('name') == '__custom_mode' and x.get('cancelled') is True for x in (native.get('extras') or [])):
        return None
    race_indexes = [i for i, row in enumerate(summary['sessions']) if row['type'] == 3]
    if race_indexes:
        index = race_indexes[-1]
        row = summary['sessions'][index]
        if row['race_completed'] is not True or row['position'] is None:
            return None
        return row['position'], native['sessions'][index]['raceResult'], 'POSITION'
    mode = summary['sessions'][-1]['type']
    pair = {4: ('bestlap', 'time'), 5: ('timeattack', 'points'), 6: ('drift', 'points'), 7: ('drag', 'wins')}.get(mode)
    if pair is None:
        return None
    extras = [x for x in (native.get('extras') or []) if isinstance(x, dict) and x.get('name') == pair[0]]
    if len(extras) != 1 or type(extras[0].get(pair[1])) is not int or extras[0][pair[1]] <= 0:
        return None
    return extras[0][pair[1]], None, 'TIME' if mode == 4 else 'POINTS'


class Session:
    """Uma tentativa já autorizada pelo jogador; sem gravação no construtor."""
    def __init__(self, cfg, history, event, catalog):
        self.path, self.history = progress_path(cfg), Path(history)
        self.event, self.catalog = event, catalog
        self.closed = False
        try:
            self.before, _ = results._read(self.path)
            _parse(self.before)
        except FileNotFoundError:
            self.before = b''
        self.progress = load(cfg)

    def finish(self, record):
        if self.closed:return None
        self.closed = True
        outcome = dict(status='unchanged', reason='completion_not_confirmed', event=self.event['id'])
        receipt = self.history/'campaign-result.json'
        if receipt.exists():return None
        try:
            if record.get('status') != 'imported':return outcome
            raw, fingerprint = results._read(self.history/'result-source.json')
            if fingerprint['sha256'] != record.get('source', {}).get('sha256'):return outcome
            native = results._json(raw)
            summary = results.parse(native, record['expected'])
            achieved = _achieved(self.event, native, summary)
            if achieved is None:return outcome
            score, order, kind = achieved
            series = self.event['series']
            index = self.event.get('event_number')
            if index is None:
                outcome['reason'] = 'unsupported_event_numbering'
                return outcome
            error = playable(self.event, self.progress, self.catalog)
            if error:
                outcome['reason'] = 'event_not_available'
                return outcome
            section = self.progress['sections'].get(series['id'].casefold(), {})
            updates = {}
            if series['championship']:
                if order is None:
                    outcome['reason'] = 'unsupported_championship_result'
                    return outcome
                if _number(section.get('EVENT'+str(index))) > 0:
                    outcome['reason'] = 'championship_round_already_recorded'
                    return outcome
                table = series['points']
                for place, car in enumerate(order):
                    key = 'POINTS' if car == 0 else 'AI'+str(car)
                    updates[key] = _number(section.get(key))+(table[place] if place < len(table) else 0)
                value = score
            else:
                conditions = self.event.get('conditions', [])
                # Race objectives are stored as POSITION; TIME and POINTS use native extras.
                if len(conditions) != 3 or any(c['objective'] < 0 or c['type'] != kind for c in conditions):
                    outcome['reason'] = 'unsupported_event_conditions'
                    return outcome
                levels = [i+1 for i, c in enumerate(conditions) if
                          (score <= c['objective'] if kind in ('TIME', 'POSITION') else score >= c['objective'])]
                value = max(levels, default=0)
                if value <= _number(section.get('EVENT'+str(index))):
                    outcome['reason'] = 'previous_best_preserved'
                    return outcome
            updates['EVENT'+str(index)] = value
            merged = dict(section, **{key: str(val) for key, val in updates.items()})
            group = next(g for g in groups(self.catalog, self.progress) if g['id'] == self.event['group_id'])
            numbers = [e['event_number'] for e in group['events'] if e.get('event_number') is not None]
            remaining = [n for n in numbers if not _number(merged.get('EVENT'+str(n)))]
            updates['EVENT'] = remaining[0] if series['championship'] and remaining else index
            goals = series['goals']
            if series['championship']:
                points = _number(merged.get('POINTS'))
                rank = 1+sum(_number(v) > points for k, v in merged.items() if re.fullmatch(r'AI\d+', k))
                complete = (goals['points'] > 0 and points >= goals['points'] or
                            goals['ranking'] > 0 and not remaining and rank <= goals['ranking'])
            else:
                tiers = [sum(_number(merged.get('EVENT'+str(n))) == tier for n in numbers) for tier in (1, 2, 3)]
                high = tiers[2]-goals['tier3']
                middle = tiers[1]+max(high, 0)-goals['tier2']
                low = tiers[0]+max(middle, 0)-goals['tier1']
                complete = high >= 0 and middle >= 0 and low >= 0 and any(goals['tier'+str(n)] for n in (1, 2, 3))
            changes = {series['id']: updates}
            if complete and series['id'].casefold() not in self.progress['complete']:
                current = self.progress['sections'].get('career', {}).get('COMPLETE', '')
                changes['career'] = {'COMPLETE': ','.join([x for x in current.split(',') if x.strip()]+[series['id']])}
            try:current, _ = results._read(self.path)
            except FileNotFoundError:current = b''
            if current != self.before:
                outcome['reason'] = 'native_progress_changed_during_session'
                return outcome
            data = _patch(current, changes)
            safe.check_components(self.path.parent)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            results._write(self.history/'career-progress-before.ini', current)
            # Recheck after writing the backup; another launcher may own this save.
            try:latest, _ = results._read(self.path)
            except FileNotFoundError:latest = b''
            if latest != current:
                outcome['reason'] = 'native_progress_changed_during_session'
                return outcome
            results._write(self.path, data, replace=True)
            outcome.update(status='saved', reason='native_rules_and_confirmed_result', value=value,
                           result='P'+str(value) if series['championship'] else MEDALS[value],
                           before_sha256=hashlib.sha256(current).hexdigest(), after_sha256=hashlib.sha256(data).hexdigest())
            return outcome
        finally:
            results._save(receipt, outcome)
