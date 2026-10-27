"""Metadados locais para escolher conteúdo; não autenticam os arquivos do jogo.

IDs conhecidos classificam entradas do catálogo. Autor, nome e tags não são
prova de origem. Não executa scripts, extrai ACD ou altera conteúdo instalado.
"""
from __future__ import annotations

import configparser
import re
from pathlib import Path

from . import file_io as safe
from . import semantic_catalogue


# IDs factuais, conferidos no índice KunosContent.json da referência CM.
# Proveniência e limites em docs/catalogue-player-experience.md.
TRACK_IDS = frozenset('drag1000 drag400 monza66 nurburgring silverstone '
    'silverstone-international silverstone-national vallelunga drift imola '
    'ks_barcelona ks_black_cat_county ks_brands_hatch ks_drag ks_highlands '
    'ks_laguna_seca ks_monza66 ks_nordschleife ks_nurburgring ks_red_bull_ring '
    'ks_silverstone ks_silverstone1967 ks_vallelunga ks_zandvoort magione monza '
    'mugello spa trento-bondone'.split())
TRACK_LAYOUTS = {
    'ks_barcelona': 'layout_gp layout_moto',
    'ks_black_cat_county': 'layout_int layout_long layout_short',
    'ks_brands_hatch': 'gp indy',
    'ks_drag': 'drag1000 drag200 drag2000 drag400 drag500',
    'ks_highlands': 'layout_drift layout_int layout_long layout_short',
    'ks_monza66': 'full junior road',
    'ks_nordschleife': 'endurance endurance_cup nordschleife touristenfahrten',
    'ks_nurburgring': 'layout_gp_a layout_gp_b layout_sprint_a layout_sprint_b',
    'ks_red_bull_ring': 'layout_gp layout_national',
    'ks_silverstone': 'gp international national',
    'ks_vallelunga': 'classic_circuit club_circuit extended_circuit',
}
ORIGINS = {'all': 'All origins', 'kunos': 'Kunos IDs',
           'mod': 'Mods / other IDs', 'unknown': 'Unknown origin'}
DRIVES = {'FWD': 'FWD · Front wheels', 'RWD': 'RWD · Rear wheels',
          'AWD': 'AWD · All wheels', 'AWD2': 'AWD · All wheels',
          '4WD': '4WD · Four wheels'}


def text(value, limit=90):
    return ' '.join(re.sub('<[^>]*>', '', value).split())[:limit] if isinstance(value, str) else ''


def tag_key(value):
    return text(value, 64).lstrip('#').strip().casefold()


def tags(info):
    values = info.get('tags')
    if not isinstance(values, list):
        return []
    unique = {}
    for value in values[:128]:
        key = tag_key(value)
        if key:
            unique.setdefault(key, text(value, 64))
    return sorted(unique.values(), key=tag_key)


def _read(path, limit):
    try:
        safe.check_components(path)
        if path.stat().st_size > limit:
            return None
        with path.open('rb') as stream:
            data = stream.read(limit+1)
        if len(data) > limit:
            return None
        return data.decode('utf-8-sig')
    except (OSError, ValueError, RuntimeError, UnicodeError):
        return None


def kunos_car_ids(game):
    raw = _read(Path(game)/'content/sfx/GUIDs.txt', 8*1024*1024)
    if raw is None:
        return None
    ids = set(re.findall(r'(?mi)^\{?[0-9a-f-]{36}\}?\s+event:/cars/([a-z0-9_-]+)/', raw))
    return {identity.casefold() for identity in ids} or None


def origin(identity, known, basis):
    value = 'unknown' if known is None else 'kunos' if identity.casefold() in known else 'mod'
    return dict(origin=value, origin_source=basis if known is not None else 'Official ID index unavailable',
                provenance='unverified')


def common(info):
    return dict(tags=tags(info), author=text(info.get('author')),
                content_version=text(info.get('version'), 40))


def power(info):
    specs = info.get('specs')
    value = specs.get('bhp') if isinstance(specs, dict) else None
    if type(value) in (int, float):
        value = str(value)
    value = text(value, 48)
    match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(bhp|whp|hp|kW|cv|PS)?', value, re.I)
    if not match or not 0 < float(match[1].replace(',', '.')) < 100000:
        return dict(power_display='Unavailable', power_source='Not supplied in metadata')
    return dict(power_display=match[1]+' '+(match[2] or 'bhp'),
                power_source='Declared · ui_car.json / specs.bhp')


def drivetrain(folder, info):
    declared_tags = info.get('tags')
    codes = {value.strip().lstrip('#').upper() for value in declared_tags
             if isinstance(value, str) and value.strip().lstrip('#').upper() in DRIVES} if isinstance(declared_tags, list) else set()
    codes = {'AWD' if value=='AWD2' else value for value in codes}
    def source(value, code):
        return value + (' · Tags disagree: '+', '.join(sorted(codes)) if codes and codes != {code} else '')
    raw = _read(Path(folder)/'data/drivetrain.ini', 128*1024)
    if raw is not None:
        try:
            ini = configparser.ConfigParser(interpolation=None)
            ini.read_string(raw)
            code = ini.get('TRACTION', 'TYPE', fallback='').strip().upper()
            if code in DRIVES:
                return dict(drive_display=DRIVES[code], drive_code=code,
                            drive_source=source('Car data · drivetrain.ini / TRACTION.TYPE',code))
        except configparser.Error:
            pass
    code = text(info.get('drivetrain'), 12).upper()
    if code in DRIVES:
        return dict(drive_display=DRIVES[code], drive_code=code,
                    drive_source=source('Declared · ui_car.json / drivetrain',code))
    if len(codes)==1:
        code = next(iter(codes))
        return dict(drive_display=DRIVES[code],drive_code=code,
                    drive_source='Declared · ui_car.json / tags')
    if len(codes)>1:
        return dict(drive_display='Unavailable',drive_code='',
                    drive_source='Conflicting declarations · ui_car.json / tags: '+', '.join(sorted(codes)))
    return dict(drive_display='Unavailable', drive_code='',
                drive_source='No readable drivetrain data; packed ACD is not extracted')


def car_info(folder, info, known):
    drive = drivetrain(folder, info)
    return dict(**common(info), **origin(folder.name, known, 'Global content/sfx/GUIDs.txt · ID match'),
                **power(info), **drive, semantic=semantic_catalogue.car(info))


def track_info(identity, layout, info):
    known = ({identity+'/'+item for item in TRACK_LAYOUTS.get(identity, '').split()}
             if layout else TRACK_IDS)
    return dict(**common(info), semantic=semantic_catalogue.track(info), **origin(identity+'/'+layout if layout else identity,
                known, 'Known Kunos track/layout IDs · snapshot 2026-10-20'))


def clean_filter(value):
    value = value if isinstance(value, dict) else {}
    selected = value.get('tags', [])
    return dict(origin=value.get('origin') if value.get('origin') in ORIGINS else 'all',
                tags=sorted({tag_key(tag) for tag in selected[:128] if tag_key(tag)})
                     if isinstance(selected, list) else [],
                match='any' if value.get('match') == 'any' else 'all')


def matches(row, value):
    value = clean_filter(value)
    if value['origin'] != 'all' and row.get('origin', 'unknown') != value['origin']:
        return False
    if not value['tags']:
        return True
    raw = row.get('tags')
    available = {tag_key(tag) for tag in raw if isinstance(tag, str)} if isinstance(raw,list) else set()
    checks = [tag in available for tag in value['tags']]
    return not checks or (any(checks) if value['match'] == 'any' else all(checks))
