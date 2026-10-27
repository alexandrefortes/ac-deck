"""Sorteio local de corridas a partir do conteúdo instalado, sem API ou escrita no jogo."""
from copy import deepcopy
from datetime import datetime, timezone
import configparser
import hashlib
import json
import os
from pathlib import Path
import random
import uuid

from . import file_io as safe
from . import content, conditions, session_settings

VARIABLE = ('car', 'track', 'layout', 'weather', 'time_minutes')
DERIVED = ('mode', 'event', 'skin')
MARKER = 'event_synthetizer'
STATE_LIMIT = 8*1024*1024


def pins(value=None):
    value = deepcopy(value) if value is not None else dict(car=None,track=None)
    if not isinstance(value,dict) or set(value) not in ({'car','track'},{'car','track','skin'}):
        raise ValueError('Invalid event pins')
    if value['car'] is not None and (not isinstance(value['car'],str) or not value['car']):
        raise ValueError('Invalid fixed car')
    if value['track'] is not None:
        if (not isinstance(value['track'],list) or len(value['track'])!=2
                or not all(isinstance(v,str) for v in value['track']) or not value['track'][0]):
            raise ValueError('Invalid fixed track/layout')
    if 'skin' in value and (not isinstance(value['skin'],str) or not value['skin'] or value['car'] is None):
        raise ValueError('A fixed livery requires a fixed car and a nonempty livery')
    return value


def candidates(catalog,base,fixed=None):
    fixed=pins(fixed)
    if 'skin' in fixed:
        car=next((row for row in catalog['cars'] if row['id']==fixed['car']),None)
        if car is None or fixed['skin'] not in car['skins']:
            raise ValueError('The fixed car or livery is no longer available.')
    groups=[dict(g,cars=[c for c in g['cars'] if fixed['car'] is None or c==fixed['car']])
            for g in catalog['synthesis_classes']]
    groups=[g for g in groups if g['cars']]
    tracks=[t for t in _tracks(catalog,base) if fixed['track'] is None or [t['id'],t['layout']]==fixed['track']]
    if not groups or not tracks or not catalog['synthesis_weather']:
        raise ValueError('No compatible race candidates. Check fixed car/track, AI lanes and grid capacity.')
    return groups,tracks


def tune(proposal, *, laps=None, ai=None, opponents=None, time_minutes=None):
    result=deepcopy(proposal)
    for key,value,low,high in (('laps',laps,1,99),('ai',ai,70,100),('opponents',opponents,0,47)):
        if value is not None:
            content.integer(value,low,high,key)
            result['base'][key]=result['selection'][key]=value
    if ai is not None:
        result['ai_level_source']='user'
    if time_minutes is not None:
        conditions.validate(dict(time_minutes=time_minutes))
        result['selection']['time_minutes']=time_minutes
        result['time_source']='user'
        if isinstance(result.get('field_sources'),dict):
            result['field_sources']['time_minutes']='user'
    return result


def options(selection,value=None):
    value=deepcopy(value) if value is not None else dict(pins=pins(),laps=selection['laps'],ai=selection['ai'])
    if not isinstance(value,dict):
        raise ValueError('Invalid event settings')
    return dict(pins=pins(value['pins']),laps=content.integer(value['laps'],1,99,'Laps'),
                ai=content.integer(value['ai'],70,100,'AI level'),
                opponents=content.integer(value.get('opponents',selection['opponents']),0,47,'Opponents'))


def matches(proposal,settings):
    return (pins(proposal.get('pins'))==settings['pins']
            and all(proposal['selection'].get(k)==settings[k] for k in ('laps','ai','opponents')))


def discover(game, *, catalog=None):
    """Enriquece uma leitura do conteúdo sem alterar o catálogo recebido."""
    game = safe.source_root(game)
    catalog = content.scan(game) if catalog is None else deepcopy(catalog)
    groups = {}
    for car in catalog['cars']:
        info = content.metadata(game/'content/cars'/car['id']/'ui/ui_car.json')
        tags = info.get('tags', [])
        labels = [v.lstrip('#').strip() for v in tags
                  if isinstance(v, str) and v.startswith('#') and v.lstrip('#').strip()] if isinstance(tags, list) else []
        origin = 'tags'
        if not labels:
            declared = info.get('class')
            labels = [declared.strip()] if isinstance(declared, str) and declared.strip() else []
            origin = 'class'
        if not labels:
            labels, origin = ['Unclassified'], 'unclassified'
        car['synthesis_classes'] = []
        for value in labels:
            value = content.label(value, 'Unclassified')[:80]
            key = origin+':'+value.casefold()
            groups.setdefault(key, dict(id=key, name=value, source=origin, cars=[]))['cars'].append(car['id'])
            car['synthesis_classes'].append(key)
    catalog['synthesis_classes'] = sorted(groups.values(), key=lambda row: row['id'])
    for track in catalog['tracks']:
        metadata = game/'content/tracks'/track['id']/'ui'
        if track['layout']:
            metadata /= track['layout']
        info = content.metadata(metadata/'ui_track.json')
        tags = info.get('tags', [])
        tags = {v.casefold() for v in tags if isinstance(v, str)} if isinstance(tags, list) else set()
        # A2B não é circuito de voltas, mesmo quando o layout contém fast_lane.ai.
        track['synthesis_race'] = 'a2b' not in tags and info.get('race') is not False
    compatible = []
    for name in catalog['weather']:
        try:
            ini = content.read_ini(game/'content/weather'/name/'weather.ini')
        except configparser.Error:
            catalog['warnings'].append('Invalid weather INI: '+name)
            continue
        # A entrega usa WeatherFX base/base, sem Sol/Pure/RainFX. Admitir somente
        # presets com a estrutura nativa, sem exigir uma lista de nomes.
        if (all(ini.has_section(s) for s in ('CLOUDS', 'FOG', 'LAUNCHER'))
                and not any(s in ini for s in ('__CSP', 'RAIN_FX', 'WEATHER_FX'))
                and not any(p.suffix.casefold() == '.lua' for p in (game/'content/weather'/name).iterdir())):
            compatible.append(name)
    catalog['synthesis_weather'] = compatible
    return catalog


def _tracks(catalog, base):
    opponents = content.integer(base.get('opponents', 5), 0, 47, 'Opponents')
    return [row for row in catalog['tracks'] if row['ai'] and row['synthesis_race'] and row['pitboxes'] > opponents]


def _selected(base, car, track, weather, minutes, *, skin=None):
    if skin is not None and skin not in car['skins']:
        raise ValueError('The fixed livery is no longer available.')
    chosen = deepcopy(base)
    chosen.update(car=car['id'], skin=car['skins'][0] if skin is None else skin, track=track['id'],
                  layout=track['layout'], weather=weather, time_minutes=minutes, mode=2, event='')
    return chosen


def generate(game, base, *, seed=None, fixed=None, catalog=None):
    """Usa o snapshot enriquecido fornecido ou descobre o conteúdo atual."""
    catalog = discover(game) if catalog is None else catalog
    base = deepcopy(base)
    base.pop(MARKER, None)
    groups,tracks = candidates(catalog,base,fixed)
    seed = random.SystemRandom().getrandbits(64) if seed is None else seed
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('Invalid event seed')
    rng = random.Random(seed)
    group = rng.choice(groups)
    car_id = rng.choice(group['cars'])
    car = next(row for row in catalog['cars'] if row['id'] == car_id)
    track = rng.choice(tracks)
    chosen = _selected(base, car, track, rng.choice(catalog['synthesis_weather']),
                       rng.randint(conditions.MINUTES_MIN, conditions.MINUTES_MAX),skin=pins(fixed).get('skin'))
    proposal = dict(schema_version=1, seed=seed, created_utc=datetime.now(timezone.utc).isoformat(),
        class_id=group['id'], class_name=group['name'], class_source=group['source'], base=base,
        selection=chosen, car_name=car['name'], track_name=track['name'],
        catalog_sha256=hashlib.sha256(json.dumps(catalog, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    if fixed is not None:
        proposal.update(schema_version=2,pins=pins(fixed))
    validate(game, proposal, catalog=catalog)
    return proposal, catalog


def validate(game, proposal, *, catalog=None):
    if (not isinstance(proposal, dict) or proposal.get('schema_version') not in (1,2)
            or not all(key in proposal for key in ('base', 'selection', 'class_id'))
            or any(not isinstance(proposal.get(key), str) for key in ('class_id', 'class_name', 'car_name', 'track_name'))):
        raise ValueError('Unsupported generated event')
    catalog = discover(game) if catalog is None else catalog
    base, chosen = proposal['base'], proposal['selection']
    if not isinstance(base, dict) or not isinstance(chosen, dict) or MARKER in base or MARKER in chosen:
        raise ValueError('Invalid event configuration')
    skin=None
    if proposal['schema_version']==2:
        fixed=pins(proposal.get('pins'))
        skin=fixed.get('skin')
        if fixed['car'] is not None and chosen.get('car')!=fixed['car']:
            raise ValueError('Generated event changed the fixed car')
        if fixed['track'] is not None and [chosen.get('track'),chosen.get('layout')]!=fixed['track']:
            raise ValueError('Generated event changed the fixed track/layout')
        content.integer(chosen.get('laps'),1,99,'Laps')
        content.integer(chosen.get('ai'),70,100,'AI level')
    group = next((row for row in catalog['synthesis_classes'] if row['id'] == proposal['class_id']), None)
    car = next((row for row in catalog['cars'] if row['id'] == chosen.get('car')), None)
    track = next((row for row in _tracks(catalog, base)
                  if (row['id'], row['layout']) == (chosen.get('track'), chosen.get('layout'))), None)
    if not group or not car or car['id'] not in group['cars'] or not track:
        raise ValueError('Generated car/class or race track is no longer available. Generate again.')
    conditions.validate(chosen)
    if chosen.get('weather') not in catalog['synthesis_weather'] or chosen.get('time_minutes') is None:
        raise ValueError('Generated weather or time is unavailable')
    if not session_settings.same(chosen, _selected(base, car, track, chosen['weather'], chosen['time_minutes'],skin=skin)):
        raise ValueError('Generated event changed fixed settings')
    return catalog


def save(path, proposal):
    path = safe.absolute(path)
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _restore_state(path, (json.dumps(proposal, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def _state_bytes(path):
    safe.check_components(path)
    if not path.exists():
        return None
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size > STATE_LIMIT:
            raise ValueError('Saved event state is too large; original files kept.')
        raw = stream.read(STATE_LIMIT+1)
        after = os.fstat(stream.fileno())
    if (safe.signature(before) != safe.signature(after)
            or safe.signature(before) != safe.signature(path.lstat())):
        raise ValueError('Saved event state changed while reading; original files kept.')
    return raw


def _sync_directory(path):
    if os.name == 'posix':
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _restore_state(path, raw):
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
    if raw is None:
        path.unlink(missing_ok=True)
        _sync_directory(path.parent)
        return
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        safe.check_components(path)
        if path.exists():
            safe.require_reference(path.lstat(), path)
        temporary.replace(path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def recover_state(store, options_path):
    """Rollback an interrupted two-file edit before loading either file."""
    if store is None or options_path is None:
        return
    store, options_path = safe.absolute(store), safe.absolute(options_path)
    if store.parent != options_path.parent or store == options_path:
        raise ValueError('Event state files must be distinct files in the same folder.')
    journal = store.with_name(store.name+'.pending-update')
    raw = _state_bytes(journal)
    if raw is None:
        return
    data = json.loads(raw)
    paths = (store, options_path)
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or not isinstance(data.get('files'), dict)
            or set(data['files']) != {path.name for path in paths}):
        raise ValueError('Invalid pending event update; original files kept.')
    restored = []
    for path in paths:
        row = data['files'][path.name]
        if (not isinstance(row, dict) or not isinstance(row.get('after_sha256'), str)
                or len(row['after_sha256']) != 64
                or any(char not in '0123456789abcdef' for char in row['after_sha256'])
                or set(row) != {'before', 'after_sha256'}
                or row['before'] is not None and not isinstance(row['before'], str)):
            raise ValueError('Invalid pending event update; original files kept.')
        before = bytes.fromhex(row['before']) if row['before'] is not None else None
        current = _state_bytes(path)
        if current != before and (current is None or hashlib.sha256(current).hexdigest() != row['after_sha256']):
            raise ValueError('Event files changed after interruption; original files kept.')
        restored.append((path, before, current != before))
    for path, before, changed in restored:
        if changed:
            _restore_state(path, before)
    journal.unlink()
    _sync_directory(journal.parent)


def save_state(store, proposal, options_path, settings):
    """Keep the previous proposal and options recoverable until both are saved."""
    recover_state(store, options_path)
    if store is None or options_path is None or proposal is None:
        if store is not None and proposal is not None:
            save(store, proposal)
        if options_path is not None:
            save(options_path, settings)
        return
    store, options_path = safe.absolute(store), safe.absolute(options_path)
    journal = store.with_name(store.name+'.pending-update')
    entries = ((store, proposal), (options_path, settings))
    before = {path: _state_bytes(path) for path, value in entries}
    after = {path: (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
             for path, value in entries}
    if any(len(raw) > STATE_LIMIT for raw in after.values()):
        raise ValueError('Event update is too large; original files kept.')
    document = dict(schema_version=1, files={path.name: dict(
        before=before[path].hex() if before[path] is not None else None,
        after_sha256=hashlib.sha256(after[path]).hexdigest())
        for path, value in entries})
    journal_raw = (json.dumps(document, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    if len(journal_raw) > STATE_LIMIT:
        raise ValueError('Event update backup is too large; original files kept.')
    save(journal, document)
    try:
        for path, value in entries:
            save(path, value)
        journal.unlink()
        _sync_directory(journal.parent)
    except Exception:
        if not journal.exists():
            _restore_state(journal, journal_raw)
        recover_state(store, options_path)
        raise


def load(path):
    path = safe.absolute(path)
    safe.check_components(path)
    return safe.read_json(path) if path.exists() else None
