"""Plano puro de prática, ancorado no CIL de AcTools; nunca grava ou inicia alvo.

Template, catálogo e caminhos são entradas explícitas. Validação própria mais
restrita que CM: IDs ASCII, controles rejeitados e seções indexadas sem lacunas.
O launcher Python reutiliza este contrato puro; as evidências investigativas
de origem não comprovam execução ou equivalência com o simulador no SteamOS.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
import math
import re


TARGET_RESOLUTIONS = ((1280, 800), (1920, 1200))
SOURCE_METHODS = ('0x060005ba', '0x060005bb', '0x06000c96', '0x06000ca0')
_NAME = re.compile(r'[A-Z_][A-Z0-9_]*\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
_CONDITIONS = {
    'TEMPERATURE': ('ROAD', 'AMBIENT'),
    'LIGHTING': ('SUN_ANGLE', 'TIME_MULT', 'CLOUD_SPEED'),
    'WIND': ('SPEED_KMH_MIN', 'SPEED_KMH_MAX', 'DIRECTION_DEG'),
    'DYNAMIC_TRACK': ('SESSION_START', 'RANDOMNESS', 'LAP_GAIN', 'SESSION_TRANSFER'),
}


@dataclass(frozen=True)
class Car:
    identifier: str
    skins: tuple[str, ...]


@dataclass(frozen=True)
class Track:
    identifier: str
    layouts: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    cars: tuple[Car, ...]
    tracks: tuple[Track, ...]
    weather_ids: tuple[str, ...]
    origin: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class PracticeRequest:
    car: str
    skin: str
    track: str
    layout: str
    driver_name: str
    nationality: str
    nation_code: str
    duration_minutes: int
    resolution: tuple[int, int]


@dataclass(frozen=True)
class PracticePlan:
    ini_text: str
    race_ini_relative: str
    executable_relative: str
    working_directory_relative: str
    arguments: tuple[str, ...]
    unset_environment: tuple[str, ...]
    resolution_intent: tuple[int, int]
    content_origin: str
    evidence_refs: tuple[str, ...]
    blocking_gates: tuple[str, ...]

    @property
    def execution_permitted(self):
        return False


def _text(value):
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Texto deve ter uma linha e não conter controles')
    # CM troca estes caracteres por '_' ao serializar Normal; aqui os rejeitamos.
    if any(c in value for c in ';[]'):
        raise ValueError('Texto contém delimitador INI não admitido pelo protótipo')
    return value


def _identifier(value, *, empty=False):
    if empty and value == '':
        return ''
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('ID inválido')
    return value.lower()


def relative_path(value):
    """Valida um caminho relativo lógico, sem consultar o filesystem."""
    _text(value)
    if not value or '\\' in value or ':' in value or value.startswith('/'):
        raise ValueError('Raiz deve ser relativa ao pacote')
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('Alias ou traversal na raiz')
    for part in parts:
        if part.endswith(('.', ' ')) or any(c in part for c in '<>"|?*'):
            raise ValueError('Alias Win32 na raiz do simulador')
        stem=part.split('.')[0].upper()
        if stem in ('CON','PRN','AUX','NUL','CONIN$','CONOUT$') or re.fullmatch(r'(COM|LPT)[1-9]',stem):
            raise ValueError('Nome reservado Win32 na raiz do simulador')
    return PurePosixPath(value)


def _number(value, label):
    if not isinstance(value,str) or not _NUMBER.fullmatch(value):
        raise ValueError('Número deve ser explícito e invariável: '+label)
    try:
        number=Decimal(value)
        native=float(number)
    except (InvalidOperation,OverflowError,ValueError) as error:
        raise ValueError('Número inválido: '+label) from error
    if not number.is_finite() or not math.isfinite(native) or (number!=0 and native==0):
        raise ValueError('Número fora da representação Double: '+label)
    return number


def _validate_output_schema(ini):
    allowed={**{s:set(keys) for s,keys in _CONDITIONS.items()},
             'DYNAMIC_TRACK':set(_CONDITIONS['DYNAMIC_TRACK'])|{'PRESET'},
             'WEATHER':{'NAME'},'HEADER':{'VERSION','__CM_FEATURE_SET'},
             'RACE':{'MODEL','MODEL_CONFIG','SKIN','TRACK','CONFIG_TRACK','AI_LEVEL','CARS',
                     'DRIFT_MODE','FIXED_SETUP','PENALTIES','JUMP_START_PENALTY'},
             'CAR_0':{'SETUP','SKIN','MODEL','MODEL_CONFIG','BALLAST','RESTRICTOR',
                      'DRIVER_NAME','NATION_CODE','NATIONALITY'},
             'SESSION_0':{'NAME','TYPE','DURATION_MINUTES','SPAWN_SET'},
             'OPTIONS':{'USE_MPH'},'LAP_INVALIDATOR':{'ALLOWED_TYRES_OUT'},
             'GHOST_CAR':{'RECORDING','PLAYING','LOAD','FILE','ENABLED','SECONDS_ADVANTAGE'},
             'GROOVE':{'VIRTUAL_LAPS','MAX_LAPS','STARTING_LAPS'}}
    for section in ('BENCHMARK','REPLAY','REMOTE','RESTART','__PREVIEW_GENERATION'):
        allowed[section]={'ACTIVE'}
    for section,values in ini.items():
        if section not in allowed or set(values)-allowed[section]:
            raise ValueError('Seção/chave não resolvida no template: '+section)
    for section,key in (('GHOST_CAR','SECONDS_ADVANTAGE'),('RACE','AI_LEVEL'),('DYNAMIC_TRACK','PRESET')):
        if key in ini[section]:
            number=_number(ini[section][key],section+'.'+key)
            if section!='GHOST_CAR' and (number!=int(number) or not -(2**31)<=number<2**31):
                raise ValueError('Inteiro do template inválido: '+section+'.'+key)


def _unique_ids(values, *, empty=False):
    if type(values) is not tuple or not values:
        raise ValueError('Catálogo deve usar tuplas não vazias')
    normalized = tuple(_identifier(v, empty=empty) for v in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError('IDs duplicados após normalização')
    return normalized


def _catalog(catalog):
    if not isinstance(catalog, Catalog) or catalog.origin not in ('synthetic', 'not_verified'):
        raise ValueError('Origem deve ser explícita; este modelo não autentica conteúdo oficial')
    if type(catalog.evidence_refs) is not tuple or not catalog.evidence_refs:
        raise ValueError('Proveniência do catálogo ausente')
    for ref in catalog.evidence_refs:
        if not _text(ref):
            raise ValueError('Referência vazia')
    if type(catalog.cars) is not tuple or type(catalog.tracks) is not tuple:
        raise ValueError('Catálogo deve ser imutável')
    if not all(isinstance(c, Car) for c in catalog.cars) or not all(isinstance(t, Track) for t in catalog.tracks):
        raise ValueError('Entrada de catálogo inválida')
    car_ids = _unique_ids(tuple(c.identifier for c in catalog.cars))
    track_ids = _unique_ids(tuple(t.identifier for t in catalog.tracks))
    cars = dict(zip(car_ids, (_unique_ids(c.skins) for c in catalog.cars)))
    tracks = dict(zip(track_ids, (_unique_ids(t.layouts, empty=True) for t in catalog.tracks)))
    return cars, tracks, _unique_ids(catalog.weather_ids)


def _template(sections):
    if type(sections) is not tuple or len(sections) > 256:
        raise ValueError('Template deve ser uma tupla de até 256 seções')
    result = {}
    for entry in sections:
        if type(entry) is not tuple or len(entry) != 2:
            raise ValueError('Seção inválida')
        section, pairs = entry
        if not isinstance(section, str) or not _NAME.fullmatch(section) or section in result:
            raise ValueError('Nome de seção inválido ou duplicado')
        if type(pairs) is not tuple:
            raise ValueError('Valores do template devem ser imutáveis')
        values = {}
        for pair in pairs:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError('Par INI inválido')
            key, value = pair
            if not isinstance(key, str) or not _NAME.fullmatch(key) or key in values:
                raise ValueError('Chave inválida ou duplicada')
            values[key] = _text(value)
        result[section] = values
    if sum(len(k)+len(v) for values in result.values() for k, v in values.items()) > 1024*1024:
        raise ValueError('Template muito grande para o protótipo')
    for prefix in ('CAR', 'SESSION', 'CONDITION'):
        indexes = sorted(int(s[len(prefix)+1:]) for s in result if re.fullmatch(prefix+r'_(0|[1-9][0-9]*)', s))
        if indexes and indexes != list(range(len(indexes))):
            raise ValueError('Lacuna nas seções indexadas: '+prefix)
        if any(s.startswith(prefix+'_') and not re.fullmatch(prefix+r'_(0|[1-9][0-9]*)', s) for s in result):
            raise ValueError('Índice ambíguo: '+prefix)
    return result


def build_practice_plan(request, catalog, template, *, game_dir, data_dir):
    """Gera texto e intenções. Não consulta filesystem, ambiente, rede ou processos.

    Template não define defaults do simulador: condições e aderência devem ser
    fornecidas. Diretório de dados ainda precisa de binding Win32 sob Linux.
    """
    if not isinstance(request, PracticeRequest):
        raise ValueError('Pedido de prática inválido')
    cars, tracks, weathers = _catalog(catalog)
    car, skin, track, layout = (_identifier(request.car), _identifier(request.skin),
                                _identifier(request.track), _identifier(request.layout, empty=True))
    if car not in cars or skin not in cars[car] or track not in tracks or layout not in tracks[track]:
        raise ValueError('Seleção ausente ou incompatível no catálogo')
    if type(request.duration_minutes) is not int or not 0 <= request.duration_minutes <= 1440:
        raise ValueError('Duração deve ser inteira entre 0 e 1440 minutos neste protótipo')
    if (type(request.resolution) is not tuple or len(request.resolution) != 2
            or any(type(v) is not int for v in request.resolution) or request.resolution not in TARGET_RESOLUTIONS):
        raise ValueError('Resolução fora do escopo 16:10')
    for value in (request.driver_name, request.nationality, request.nation_code):
        if not _text(value):
            raise ValueError('Identificação sintética do piloto deve ser explícita')
    game, data = relative_path(game_dir), relative_path(data_dir)
    game_alias,data_alias=PurePosixPath(game.as_posix().casefold()),PurePosixPath(data.as_posix().casefold())
    if game_alias == data_alias or game_alias in data_alias.parents or data_alias in game_alias.parents:
        raise ValueError('Raízes de programa/dados não podem se sobrepor')
    ini = _template(template)
    if 'ASSISTS' in ini:
        raise ValueError('Assistências pertencem a assists.ini separado; este gerador produz só race.ini')
    for section, keys in _CONDITIONS.items():
        for key in keys:
            value = ini.get(section, {}).get(key)
            _number(value,section+'.'+key)
    if Decimal(ini['WIND']['SPEED_KMH_MIN'])>Decimal(ini['WIND']['SPEED_KMH_MAX']):
        raise ValueError('Intervalo de vento invertido')
    weather = _identifier(ini.get('WEATHER', {}).get('NAME'))
    if weather not in weathers:
        raise ValueError('Weather do template ausente no catálogo')
    ini['WEATHER']['NAME'] = weather
    for section in ('BENCHMARK', 'REPLAY', 'REMOTE', 'RESTART', '__PREVIEW_GENERATION'):
        ini.setdefault(section, {})['ACTIVE'] = '0'
    removals = {'REMOTE': ('__FEATURES', '__CM_EXTENDED'),
                'LIGHTING': ('__CM_WEATHER_TYPE', '__CM_WEATHER_CONTROLLER', '__CM_DATE',
                             '__CM_DATE_USE_TIME', '__CM_WEATHER_HUMIDITY', '__CM_WEATHER_PRESSURE'),
                'RACE': ('__CM_CUSTOM_MODE',), 'OPTIONS': ('__BACKGROUND_IMAGE',)}
    for section, keys in removals.items():
        for key in keys:
            ini.setdefault(section, {}).pop(key, None)
    for prefix, start in (('CAR', 1), ('SESSION', 0), ('CONDITION', 0)):
        while prefix+'_'+str(start) in ini:
            del ini[prefix+'_'+str(start)]
            start += 1
    for section in ('EVENT', 'SPECIAL_EVENT'):
        ini.pop(section, None)
    ini.setdefault('HEADER', {}).update(VERSION='2', __CM_FEATURE_SET='2')
    ini.setdefault('LAP_INVALIDATOR', {})['ALLOWED_TYRES_OUT'] = '-1'
    race = ini.setdefault('RACE', {})
    race.update(MODEL=car, MODEL_CONFIG='', SKIN=skin, TRACK=track, CONFIG_TRACK=layout)
    race.setdefault('AI_LEVEL', '100')
    ini['CAR_0'] = dict(SETUP='', SKIN=skin, MODEL='-', MODEL_CONFIG='', BALLAST='0', RESTRICTOR='0',
                        DRIVER_NAME=request.driver_name, NATION_CODE=request.nation_code, NATIONALITY=request.nationality)
    ini.setdefault('OPTIONS', {})['USE_MPH'] = '0'
    race.update(CARS='1', DRIFT_MODE='0', FIXED_SETUP='0', PENALTIES='1', JUMP_START_PENALTY='0')
    ini.setdefault('GHOST_CAR', {}).update(RECORDING='0', PLAYING='0', LOAD='0', FILE='', ENABLED='0')
    ini['GROOVE'] = dict(VIRTUAL_LAPS='10', MAX_LAPS='30', STARTING_LAPS='0')
    ini['SESSION_0'] = dict(NAME='Practice', TYPE='1', DURATION_MINUTES=str(request.duration_minutes), SPAWN_SET='PIT')
    _validate_output_schema(ini)
    # Formato canônico próprio: LF e ordem lexical. Não promete bytes iguais ao CM.
    text = '\n'.join('['+section+']\n'+'\n'.join(key+'='+ini[section][key] for key in sorted(ini[section]))+'\n'
                     for section in sorted(ini))
    return PracticePlan(text, (data/'Assetto Corsa/cfg/race.ini').as_posix(),
                        (game/'acs.exe').as_posix(), game.as_posix(), (),
                        ('PYTHONHOME', 'PYTHONOPTIMIZE', 'PYTHONPATH'), request.resolution,
                        catalog.origin, catalog.evidence_refs,
                        ('official_content_and_hashes', 'native_x64_dependencies_and_entry',
                         'win32_paths_under_linux_and_all_writes', 'portable_data_mapping',
                         'baseline_without_csp', 'compatibility_command', 'real_display_mode',
                         'explicit_assists_video_controls'))
