"""Catálogo local e configurações offline; não inicia processos ou muda a origem."""
import configparser
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile

from . import file_io as safe, game_config
from . import controls, graphics, conditions, comfort, catalogue

IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
CATALOG_VERSION = 2
MODES = (('Practice', 1, 'PIT'), ('Hotlap', 4, 'HOTLAP_START'),
         ('Race', 3, 'START'), ('Time Attack', 5, 'START'), ('Drift', 6, 'START'))


def pp_filters(game):
    """Enumera apenas filtros instalados; não copia filtros de terceiros."""
    root = Path(game)/'system/cfg/ppfilters'
    safe.check_components(root)
    if not root.exists():
        return []
    names = {}
    for path in sorted(root.iterdir(),key=lambda path:path.name.casefold()):
        if path.suffix.casefold() != '.ini':
            continue
        safe.check_components(path)
        safe.require_reference(path.lstat(),path)
        key = path.stem.casefold()
        if key in names:
            raise ValueError('Ambiguous installed PP filter: '+path.stem)
        names[key] = path.stem
    return list(names.values())


def identifier(value, *, empty=False):
    if empty and value == '':
        return value
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Identificador de conteúdo inválido')
    return value


def read_ini(path):
    safe.check_components(path)
    result = configparser.ConfigParser(interpolation=None, strict=False,
                                     inline_comment_prefixes=(';',))
    result.optionxform = str.upper
    result.read_string(path.read_text('utf-8-sig', errors='replace'))
    return result


def ini_bytes(ini):
    output = io.StringIO()
    ini.write(output, space_around_delimiters=False)
    return output.getvalue().encode('utf-8')


def metadata(path):
    if not path.is_file():
        return {}
    safe.check_components(path)
    try:
        # Os JSONs originais podem conter quebras de linha dentro de description.
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Alguns metadados distribuídos, incluindo Nordschleife, usam
            # Windows-1252 (por exemplo, o símbolo ° em geotags).
            text = raw.decode('cp1252')
        value = json.loads(text, strict=False)
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeError):
        return {}


def folders(path):
    if not path.is_dir():
        return []
    safe.check_components(path)
    result = []
    for item in sorted(path.iterdir()):
        safe.check_components(item)
        if item.is_dir() and IDENTIFIER.fullmatch(item.name):
            result.append(item)
    return result


def label(value, fallback):
    value = re.sub('<[^>]*>', '', str(value or fallback))
    return ' '.join(value.split())[:180] or fallback


def scan(game):
    """Lista o conteúdo presente, sem presumir licença ou procedência por nome."""
    game = Path(game)
    cars, tracks, events, warnings = [], [], [], []
    known_cars = catalogue.kunos_car_ids(game)
    for folder in folders(game/'content/cars'):
        skins = [p.name for p in folders(folder/'skins')]
        if not skins or not (folder/'data.acd').is_file() and not (folder/'data').is_dir():
            warnings.append('Carro incompleto: '+folder.name)
            continue
        info = metadata(folder/'ui/ui_car.json')
        cars.append(dict(id=folder.name, name=label(info.get('name'), folder.name),
                         brand=label(info.get('brand'), ''), skins=skins,
                         **catalogue.car_info(folder, info, known_cars)))
    for folder in folders(game/'content/tracks'):
        variants = []
        if (folder/'ui/ui_track.json').is_file():
            variants.append(('', folder/'ui/ui_track.json'))
        variants.extend((p.name, p/'ui_track.json') for p in folders(folder/'ui')
                        if (p/'ui_track.json').is_file())
        for layout, path in variants:
            info = metadata(path)
            try:
                boxes = max(1, int(info.get('pitboxes', 1)))
            except (ValueError, TypeError):
                boxes = 1
            tracks.append(dict(id=folder.name, layout=layout,
                key=folder.name+'|'+layout, name=label(info.get('name'), folder.name),
                country=label(info.get('country'), ''), pitboxes=boxes,
                ai=(folder/layout/'ai/fast_lane.ai').is_file(),
                **catalogue.track_info(folder.name, layout, info)))
    weather = [p.name for p in folders(game/'content/weather') if (p/'weather.ini').is_file()]
    car_ids = {p['id'] for p in cars}
    track_keys = {p['key'] for p in tracks}
    from . import campaigns
    paths = sorted((game/'content/specialevents').glob('*/event.ini'))
    paths += sorted((game/'content/career').glob('*/event*/event.ini'))
    for path in paths:
        try:
            ini = read_ini(path)
            if 'RACE' not in ini or 'SESSION_0' not in ini:
                continue
            race = ini['RACE']
            event_info = campaigns.event_metadata(path, ini)
            available = race.get('MODEL') in car_ids and race.get('TRACK', '')+'|'+race.get('CONFIG_TRACK', '') in track_keys
            if not available:
                warnings.append('Evento com conteúdo ausente: '+path.relative_to(game).as_posix())
            events.append(dict(id=path.relative_to(game).as_posix(),
                name=label(ini.get('EVENT', 'NAME', fallback=''), path.parent.name),
                group=event_info['series']['name'] if event_info['series'] else 'Special events',
                car=race.get('MODEL'), track=race.get('TRACK'), layout=race.get('CONFIG_TRACK', ''),
                available=available, unavailable_reason='' if available else 'Required car or track is not installed',
                **event_info))
        except (OSError, ValueError, configparser.Error):
            warnings.append('Evento com definição ilegível: '+path.relative_to(game).as_posix())
    return dict(catalog_version=CATALOG_VERSION,cars=sorted(cars, key=lambda p:p['name'].casefold()),
                tracks=sorted(tracks, key=lambda p:p['name'].casefold()), weather=weather,
                events=events, warnings=warnings, official_origin_status='not_verified')


def integer(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(name+' fora do intervalo')
    return value


def session(game, catalog, selection, *, csp=False, cfg=None, base_cfg=None, xinput=False):
    """Gera prática, corrida ou evento instalado a partir do perfil já funcional."""
    cfg = Path(cfg) if cfg is not None else Path(game)/'state/Assetto Corsa/cfg'
    def read(name):
        path=cfg/name
        if not path.exists() and base_cfg is not None:
            path=Path(base_cfg)/name
        return read_ini(path)
    race = configparser.ConfigParser(interpolation=None)
    race.optionxform = str.upper
    race.read_string(game_config.profile_texts(Path(game))['race.ini'].decode('utf-8'))
    event_id = selection.get('event', '')
    if event_id:
        item = next((p for p in catalog['events'] if p['id'] == event_id), None)
        if item is None:
            raise ValueError('Evento ausente do catálogo')
        event_path = Path(game)/item['id']
        event = read_ini(event_path)
        for section in event.sections():
            race[section] = dict(event[section])
        car_id, track_id, layout = item['car'], item['track'], item['layout']
        # Algumas séries deixam os adversários num arquivo compartilhado.
        opponent_path = event_path.parent.parent/'opponents.ini'
        total = int(race.get('RACE', 'CARS', fallback='1'))
        if total > 1 and not race.has_section('CAR_1') and opponent_path.is_file():
            opponents = read_ini(opponent_path)
            for index in range(1, total):
                key = 'AI'+str(index)
                if key not in opponents:
                    raise ValueError('Adversário ausente no evento: '+key)
                other = opponents[key]
                race['CAR_'+str(index)] = dict(MODEL=other.get('MODEL', other.get('CAR', car_id)),
                    SKIN=other.get('SKIN', ''), DRIVER_NAME=other.get('DRIVER_NAME', other.get('NAME', 'AI '+str(index))),
                    AI_LEVEL=other.get('AI_LEVEL', other.get('LEVEL', '100')), MODEL_CONFIG=other.get('MODEL_CONFIG', ''),
                    SETUP='', BALLAST='0', RESTRICTOR='0')
    else:
        car_id = identifier(selection['car'])
        track_id = identifier(selection['track'])
        layout = identifier(selection.get('layout', ''), empty=True)
    car = next((p for p in catalog['cars'] if p['id'] == car_id), None)
    track = next((p for p in catalog['tracks'] if (p['id'],p['layout']) == (track_id,layout)), None)
    if not car or not track:
        raise ValueError('Carro ou pista ausente do catálogo')
    if not event_id:
        skin = selection.get('skin', car['skins'][0])
        if skin not in car['skins']:
            raise ValueError('Pintura ausente do carro')
        mode = integer(selection.get('mode', 0), 0, len(MODES)-1, 'Modo')
        _, session_type, spawn = MODES[mode]
        opponents = integer(selection.get('opponents', 5), 0, min(47,track['pitboxes']-1), 'Adversários') if session_type == 3 else 0
        if opponents and not track['ai']:
            raise ValueError('A pista não tem linha de IA; use uma sessão solo')
        total = opponents+1
        race['RACE'] = dict(MODEL=car_id, MODEL_CONFIG='', SKIN=skin,
            TRACK=track_id, CONFIG_TRACK=layout, CARS=str(total),
            AI_LEVEL=str(integer(selection.get('ai', 90), 70, 100, 'Nível IA')),
            DRIFT_MODE='1' if session_type == 6 else '0', FIXED_SETUP='0',
            PENALTIES='1', JUMP_START_PENALTY='0')
        for index in range(total):
            race['CAR_'+str(index)] = dict(MODEL='-' if index == 0 else car_id,
                SKIN=skin if index == 0 else car['skins'][index % len(car['skins'])],
                MODEL_CONFIG='', SETUP='', BALLAST='0', RESTRICTOR='0',
                DRIVER_NAME='Piloto' if index == 0 else 'Piloto '+str(index),
                # O nivel individual multiplica RACE.AI_LEVEL no controlador nativo.
                # Manter 100 aqui aplica a escolha global somente uma vez.
                NATIONALITY='Brazil', NATION_CODE='BRA', AI_LEVEL='100')
        race['SESSION_0'] = dict(NAME=MODES[mode][0], TYPE=str(session_type), SPAWN_SET=spawn,
            DURATION_MINUTES=str(integer(selection.get('minutes', 20), 0, 180, 'Minutos')) if session_type == 1 else '0')
        if session_type == 3:
            race['SESSION_0'].update(LAPS=str(integer(selection.get('laps', 5), 1, 99, 'Voltas')), STARTING_POSITION=str(total))
        weather = selection.get('weather', '3_clear')
        if weather not in catalog['weather']:
            raise ValueError('Clima ausente do catálogo')
        race['WEATHER'] = dict(NAME=weather)
    for section in ('REMOTE', 'REPLAY', 'BENCHMARK', 'RESTART', '__PREVIEW_GENERATION'):
        race[section] = dict(ACTIVE='0')
    race['HEADER'] = dict(VERSION='2')
    race['RACE'].update(MODEL=car_id, TRACK=track_id, CONFIG_TRACK=layout)
    # Eventos conservam seus campos/condições; validar todos os carros selecionados.
    total = int(race['RACE']['CARS'])
    if not 1 <= total <= track['pitboxes']:
        raise ValueError('Grid do evento excede os boxes da pista')
    car_map = {p['id']:p for p in catalog['cars']}
    for index in range(total):
        name = 'CAR_'+str(index)
        if name not in race:
            raise ValueError('Configuração de grid incompleta: '+name)
        model = race[name].get('MODEL', '-')
        model = car_id if model == '-' else model
        if model not in car_map:
            raise ValueError('Carro/pintura do evento indisponível: '+name)
        skin=race[name].get('SKIN', '')
        choices={s.casefold():s for s in car_map[model]['skins']}
        if not skin:
            skin=car_map[model]['skins'][0]
        if skin.casefold() not in choices:
            raise ValueError('Carro/pintura do evento indisponível: '+name)
        race[name]['SKIN']=choices[skin.casefold()]
    conditions.apply(race, selection, csp=csp)
    conditions.apply_track(race)
    assists = read('assists.ini')
    assists['ASSISTS']['AUTO_SHIFTER'] = '1' if selection.get('automatic', True) else '0'
    assists['ASSISTS']['AUTO_CLUTCH'] = '1' if selection.get('automatic', True) else '0'
    video = read('video.ini')
    resolution = tuple(selection.get('resolution', (1280,800)))
    if resolution not in ((1280,800),(1920,1200)):
        raise ValueError('Resolução fora do escopo')
    # O perfil inicial 010 usa janela. Não herdar esse estado ao trocar a
    # resolução: no compositor do Deck, janela e área de render podem divergir
    # e deixar os cliques fora dos botões da interface nativa. A sessão usa a
    # mesma apresentação em tela cheia nos dois perfis e nas duas dimensões.
    video['VIDEO'].update(WIDTH=str(resolution[0]), HEIGHT=str(resolution[1]), FULLSCREEN='1')
    if 'graphics_profile' in selection:
        graphics.apply(video, selection['graphics_profile'], csp=csp, selection=selection)
    comfort.apply_native(video, assists, selection)
    if selection.get('pp_filter') is not None:
        selected = selection['pp_filter']
        names = {name.casefold(): name for name in pp_filters(game)}
        if not isinstance(selected,str) or selected.casefold() not in names:
            raise ValueError('Selected PP filter is not installed')
        if 'POST_PROCESS' not in video:
            video.add_section('POST_PROCESS')
        video['POST_PROCESS']['FILTER'] = names[selected.casefold()]
    controls.validate(selection)
    if 'hide_driver_arms' in selection:
        if 'ASSETTOCORSA' not in video:
            video.add_section('ASSETTOCORSA')
        video['ASSETTOCORSA']['HIDE_ARMS'] = '1' if selection['hide_driver_arms'] else '0'
    texts = {'race.ini':ini_bytes(race), 'assists.ini':ini_bytes(assists), 'video.ini':ini_bytes(video)}
    candidates = [cfg/'gameplay.ini']
    if base_cfg is not None:
        candidates.append(Path(base_cfg)/'gameplay.ini')
    candidates.append(Path(game)/'cfg/gameplay.ini')
    path = next((path for path in candidates if path.exists()), None)
    gameplay = read_ini(path) if path is not None else configparser.ConfigParser(interpolation=None)
    if selection.get('virtual_steer_degrees') is not None:
        if 'STEER_ANIMATION' not in gameplay:
            gameplay.add_section('STEER_ANIMATION')
        gameplay['STEER_ANIMATION']['MAX_DEGREES'] = str(selection['virtual_steer_degrees'])
    if 'VIRTUAL_MIRROR' not in gameplay:
        gameplay.add_section('VIRTUAL_MIRROR')
    gameplay['VIRTUAL_MIRROR']['ACTIVE'] = '0'
    if 'OVERLAY_LEADERBOARD' not in gameplay:
        gameplay.add_section('OVERLAY_LEADERBOARD')
    gameplay['OVERLAY_LEADERBOARD']['ACTIVE'] = '0'
    texts['gameplay.ini'] = ini_bytes(gameplay)
    if (xinput or any(selection.get(key) is not None for key in controls.FIELDS)
            or selection.get('steer_gamma_tenths') is not None
            or any(key in selection for key in controls.BINDINGS)):
        ini = read('controls.ini')
        if xinput:
            if 'HEADER' not in ini:
                ini.add_section('HEADER')
            ini['HEADER']['INPUT_METHOD']='X360'
        controls.apply(ini, selection)
        texts['controls.ini'] = ini_bytes(ini)
    return texts


def write_session(game, catalog, selection, history, *, csp=False, cfg=None, base_cfg=None, xinput=False):
    """Aplica ao cfg declarado; guarda as configurações anteriores por sessão."""
    game, history = Path(game), Path(history)
    texts = session(game, catalog, selection, csp=csp,cfg=cfg,base_cfg=base_cfg,xinput=xinput)
    cfg = Path(cfg) if cfg is not None else game/'state/Assetto Corsa/cfg'
    safe.check_components(cfg)
    safe.check_components(history)
    history.mkdir(parents=True, exist_ok=False)
    safe.check_components(history)
    cfg.mkdir(parents=True,exist_ok=True)
    hashes = {}
    for name, data in texts.items():
        path = cfg/name
        safe.check_components(path)
        if path.exists():
            safe.require_reference(path.lstat(), path)
            (history/('previous-'+name)).write_bytes(path.read_bytes())
        (history/name).write_bytes(data)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', prefix=name+'.', suffix='.launcher-new',
                                             dir=cfg, delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes
