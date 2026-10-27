"""CSP fixado: payload local, instalação declarada e overrides por sessão.

Não baixa componentes nem executa DLLs. Acrescenta só o patch selecionado.
Os defaults e scripts de terceiros permanecem intactos. Ver docs/build-csp.md.
"""
import configparser
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import stat
import sys
import uuid
import zipfile

from . import file_io as safe
from . import controls, installed, graphics, graphics_settings, comfort, chase_camera

VERSION = '0.3.0-preview728'
BUILD_CODE = 4263
ARCHIVE_SHA256 = 'b645eb1faa8291f538cda56dca17aa4e09ebe1bd8be23e8ce0f2dfef209034d9'
URL = 'mods/lights-patch-v0.3.0-preview728-full.zip'
PREVIOUS_VERSION = '0.2.11'
PREVIOUS_ARCHIVE_SHA256 = '0729ccaebb403a7a6d1c40516990da8116cb5f56eea4c1fe0bdd29863a5a6ffb'
AI_LABELS = {'original': 'Original', 'improved': 'Improved (CSP)'}
COMMON = {
    'general.ini': {'BASIC': {'ENABLED': '1'}, 'OPTIMIZATIONS': {'CACHE_ACS': '1'},
                    'OPTIMIZATIONS_GPU': {'OPTIMIZE_MESHES':'1',
                        'DEDUPLICATE_MESHES':'1', 'DEDUPLICATE_TEXTURES':'0',
                        'UPGRADE_TEXTURES':'0', 'BC7_CACHE2':'1', 'QUERY_BASED_MAPPING2':'1'},
                    'PHYSICS_EXPERIMENTS': {'EXTENDED_PHYSICS': '1'}},
    'graphics_adjustments.ini': {
        'BASIC': {'FORCE_FXAA2': '1'},
        'ANTIALIASING': {'MODE': 'DISABLED'},
        'ANTIALIASING_MSAA': {'CUSTOM_RESOLVE': '1', 'CUSTOM_KERNEL': '0'},
        'FSR': {'ACTIVE': '0'}, 'RENDER_SCALE': {'SCALE': '1'},
        'LODS': {'COCKPIT_LR_FIX': '1', 'DRIVER_LR_FIX': '1',
                 'CARS_DISTANCE_MULT': '1', 'TRACK_DISTANCE_MULT': '1',
                 'TREES_DISTANCE_MULT': '1', 'FORCE_LOD_B': '0',
                 'TREAT_TRACK_CAMERAS_THE_SAME': '1', 'FALLBACK_LODS': '0',
                 'LODLESS_LIMIT': '40', 'HIDE_DISTANT_DRIVERS': '1',
                 'HIDE_WHEELS_FOR_INTERIOR_VIEW': '0',
                 'SKIP_LOADING_FIRST_LOD_FOR_OTHER_CARS': '0', 'LIMIT_VISIBLE_CARS': '1'}},
    'neck.ini': {'BASIC': {'ENABLED': '1'}},
    'smart_shadows.ini': {
        'BASIC': {'ENABLED': '0', 'AUTOMATIC_SPLITS': '1'},
        'CUSTOM_SHADOW_MATRICES': {'FOURTH_CASCADE': '0'}},
    'reflections_fx.ini': {'MAIN_CUBEMAP': {'RESOLUTION2': '512', 'REPROJECT_PARTIAL': '1'}},
    'extra_fx.ini': {'BASIC': {'ENABLED': '0'}, 'MOTION_BLUR': {'ENABLED': '0'}},
    'grass_fx.ini': {'BASIC': {'QUALITY': '1'},
                     'RENDERING': {'CAST_SHADOWS': '0', 'EXTRAFX_PASS': '0', 'SMOOTHER_BLENDING': '0'}},
    'particles_fx.ini': {
        'SMOKE': {'USE_CULLING': '1', 'SHOW_IN_MIRRORS': '0', 'NEW_HEATING': '0',
                  'CAST_SHADOWS': '0', 'CAST_AMBIENT_SHADOWS': '0'},
        'FIREWORKS': {'ENABLED': '0'}, 'AC_PARTICLES': {'REWORKED_HEAT_SHIMMER': '0'}},
    'lighting_fx.ini': {'SHADOWS': {'ENABLED': '0', 'HIGH_QUALITY_HEADLIGHT_SHADOWS': '0'},
                         'PERFORMANCE': {'ENABLE_REFLECTION_LIGHT': '0'}},
    'weather_fx.ini': {
        'BASIC': {'ENABLED': '1', 'CONTROLLER': 'base', 'IMPLEMENTATION': 'base'},
        'PERFORMANCE': {'ADDITIONAL_EFFECTS': '0', 'DETAILED_CLOUD_SHADOWS': '0',
                        'SLOW_REFLECTIONS_UPDATE': '1'},
        'PP_TWEAKS': {'FULL_RESOLUTION': '0'}},
    'smart_mirror.ini': {'REAL_MIRRORS': {'ENABLED': '0'}, 'PERFORMANCE': {'SKIP_FRAMES': '0'}},
    'gamepad_fx.ini': {
        'BASIC': {'ENABLED': '1'},
        'JOYPAD_ASSIST': {'IMPLEMENTATION': 'gamepad_force'},
        'ADVANCED_GAMEPADS': {'ENABLED': '0', 'BLOCK_STEAM': '0',
                             'AUTODETECT': '0', 'AUTODETECT_DUALSHOCK': '0'}},
    'track_adjustments.ini': {'MISCELLANEOUS': {'USE_FLAGS_CLOTH': '0'}},
    'new_behaviour.ini': {
        'AI2': {'ENABLED': '0'},
        'AI_TWEAKS': {'FIX_SHORT_AXLE': '1', 'FIX_LOW_LEVEL': '1', 'START_REDUCE_REDLINING': '1',
                      'START_STRAIGHTEN_TRAJECTORY': '1', 'CAUTIOUS_STEERING': '1',
                      'REMOVE_STEER_LOOKAHEAD_SPEED_LIMIT': '1',
                      'ACT_IMPATIENT': '1', 'TRAJECTORIES_FOR_DUMMIES': '1',
                      'FIX_UPSHIFT_THRESHOLD': '0', 'FIX_DOWNSHIFT_THRESHOLD': '0',
                      'STOP_TELEPORTING_STUCK': '1'},
        'AI_FLOOD': {'ENABLED': '0'},
        'WRONG_WAY': {'ALLOW_IN_PRACTICE': '0', 'ALLOW_IN_TRACKDAY': '0'},
        'RAIN': {'AVOID_SIDES': '0', 'AVOID_PUDDLES': '0'},
        'AI_RACE_RUBBERBANDING': {'ENABLED': '1'},
        'AI_RACE_COOLDOWN': {'ENABLED': '0'},
        'AI_SPLINES': {'ALT_GRID': '1', 'CACHE_PAYLOADS': '1',
                       'FIX_REVERSED': '1', 'ALT_DRAG_SPLINE': '0'}},
}
OBSOLETE_OVERRIDES = {
    'general.ini': {'OPTIMIZATIONS_CPU': ('FLATTEN_NODES',),
                    'OPTIMIZATIONS_GPU': ('OPTIMIZE_MESHES_MORE', 'BC7_CACHE', 'QUERY_BASED_MAPPING'),
                    'FPS_LIMIT_TWEAKS': ('USE_ADJUSTED_FRAME_TIME', 'USE_SLEEP')},
    'graphics_adjustments.ini': {'BASIC': ('ENABLED', 'FORCE_FXAA')},
    'lighting_fx.ini': {'BASIC': ('ENABLED',)},
    'gamepad_fx.ini': {'AXIS_REMAP': ('THROTTLE', 'BRAKES')},
    'new_behaviour.ini': {'AI_RACE_ADAPTATION': ('ENABLED',)},
}


def digest(path):
    return safe.hash_reference_file(Path(path))[0]


def parser(raw=''):
    ini = configparser.ConfigParser(interpolation=None, strict=False,
                                    inline_comment_prefixes=(';',))
    ini.optionxform = str.upper
    if raw:
        ini.read_string(raw)
    return ini


def overrides(profile, control_mode, ai_behavior='improved', ai_experimental=False):
    graphics.base_profile(profile)
    controls.validate(dict(control_mode=control_mode))
    if ai_behavior not in AI_LABELS:
        raise ValueError('Modo de IA CSP desconhecido')
    if type(ai_experimental) is not bool:
        raise ValueError('Experimental AI must be On or Off')
    result = {name: {section: dict(values) for section, values in sections.items()}
              for name, sections in COMMON.items()}
    # Base CSP comum aos dois perfis. Quality difere nos ajustes nativos.
    result['smart_shadows.ini']['BASIC']['AUTOMATIC_SPLITS_DISTANCE'] = str(graphics.profile_shadow_distance(profile))
    if profile == 'csp_performance':
        result['graphics_adjustments.ini']['BASIC']['FORCE_FXAA2'] = '0'
        result['general.ini']['OPTIMIZATIONS_GPU']['DEDUPLICATE_TEXTURES'] = '1'
        result['general.ini']['OPTIMIZATIONS']['CACHE_CSP_CONFIGS'] = '1'
        result['general.ini']['OPTIMIZATIONS_CPU'] = {
            'USE_CHUNKS': '2', 'POSTPONABLE_OPTIONALS': '1', 'HYPERTHREADING_FIX': '0'}
    result['grass_fx.ini']['BASIC']['ENABLED'] = '0'
    result['particles_fx.ini']['SMOKE'].update(
        USE_DOWNSCALING='1', SIMPLIFIED_SHADING='1')
    result['lighting_fx.ini']['PERFORMANCE']['CARS_WITH_LIGHTS'] = '6'
    result['weather_fx.ini']['PERFORMANCE'].update(
        HIGH_QUALITY_STARS='0', EXTRA_CLOUDS_FIDELITY='0')
    result['gamepad_fx.ini']['JOYPAD_ASSIST']['ENABLED'] = '1' if control_mode == 'assisted' else '0'
    result['new_behaviour.ini']['BASIC'] = {'ENABLED':'1' if ai_behavior == 'improved' else '0'}
    result['new_behaviour.ini']['AI2']['ENABLED'] = '1' if ai_behavior == 'improved' and ai_experimental else '0'
    return result


def unpack(archive, destination):
    """Admite apenas o ZIP selecionado. Não extrai nomes arbitrários ou links."""
    archive, destination = Path(archive), Path(destination)
    expected = digest(archive)
    if expected != ARCHIVE_SHA256:
        raise ValueError('SHA-256 do ZIP CSP difere da versão selecionada')
    safe.check_components(destination)
    if destination.exists():
        raise FileExistsError('Destino CSP já existe')
    with zipfile.ZipFile(archive) as source:
        files, names, total = [], set(), 0
        for item in source.infolist():
            name = safe.relative_file(item.filename.rstrip('/'))
            if name != 'dwrite.dll' and not name.startswith('extension/') and name != 'extension':
                raise ValueError('Raiz inesperada no ZIP CSP: '+name)
            if name.casefold() in names or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                raise ValueError('Entrada ambígua ou link no ZIP CSP: '+name)
            names.add(name.casefold())
            if not item.is_dir():
                total += item.file_size
                files.append((name, item))
        if total > 256*1024*1024 or not any(n == 'dwrite.dll' for n, _ in files):
            raise ValueError('Conteúdo CSP fora da seleção esperada')
        destination.mkdir(parents=True)
        rows = []
        for name, item in files:
            path = destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open(item) as src, path.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            rows.append(dict(path=name, sha256=digest(path), size_bytes=path.stat().st_size))
    if digest(archive) != expected:
        raise ValueError('ZIP CSP mudou durante a cópia')
    manifest = dict(schema_version=1, version=VERSION, archive_sha256=expected,
                    source_url=URL, files=rows,
                    provenance='Arquivo Patreon fornecido pelo usuário via Git LFS; '
                               'SHA-256 confere o objeto recebido, sem assinatura independente')
    safe.write_new_json(destination/'manifest.json', manifest)
    check_profiles(destination)
    return manifest


def check_profiles(payload):
    """Cada chave precisa existir na distribuição efetiva, não só no configrepo."""
    for profile in ('csp_performance', 'csp_quality'):
        settings=overrides(profile, 'assisted')
        comfort.apply_csp(settings, comfort.DEFAULTS)
        chase_camera.apply_csp(settings, chase_camera.DEFAULTS)
        for name, sections in settings.items():
            raw = (Path(payload)/'extension/config'/name).read_text('utf-8-sig')
            ini = parser(raw)
            for section, values in sections.items():
                for key in values:
                    if section not in ini or key not in ini[section]:
                        # Chaves ocultas declaradas, na seção efetiva deste ZIP.
                        hidden = {('general.ini', 'OPTIMIZATIONS', 'CACHE_ACS'),
                                  ('general.ini', 'OPTIMIZATIONS_GPU', 'BC7_CACHE2'),
                                  ('general.ini', 'OPTIMIZATIONS_GPU', 'QUERY_BASED_MAPPING2'),
                                  ('graphics_adjustments.ini', 'BASIC', 'FORCE_FXAA2')}
                        if (name, section, key) in hidden:
                            block = re.search(r'(?ms)^\['+re.escape(section)+r'\]\s*\n(.*?)(?=^\[|\Z)', raw)
                            if block and re.search(r'(?m)^\s*;\s*'+re.escape(key)+r'\s*=\s*1\b', block[1]):
                                continue
                        raise ValueError('Chave ausente nesta versão CSP: '+name+'/'+section+'/'+key)
    for relative in ('extension/lua/joypad-assist/gamepad_force/assist.lua',
                     'extension/weather/base/weather.lua',
                     'extension/weather-controllers/base/controller.lua'):
        if not (Path(payload)/relative).is_file():
            raise ValueError('Script CSP necessário ausente: '+relative)


def verify(payload):
    payload = safe.source_root(payload)
    manifest = safe.read_json(payload/'manifest.json')
    if manifest.get('version') != VERSION or manifest.get('archive_sha256') != ARCHIVE_SHA256:
        raise ValueError('Manifesto CSP não corresponde ao build selecionado')
    seen = set()
    for row in manifest['files']:
        name = safe.relative_file(row['path'])
        if name.casefold() in seen or (name != 'dwrite.dll' and not name.startswith('extension/')):
            raise ValueError('Seleção CSP inválida')
        seen.add(name.casefold())
        if digest(payload/name) != row['sha256'] or (payload/name).stat().st_size != row['size_bytes']:
            raise ValueError('Payload CSP mudou: '+name)
    if 'dwrite.dll' not in seen:
        raise ValueError('Payload CSP incompleto')
    check_profiles(payload)
    return manifest


def _managed_rows(manifest):
    rows = {}
    for row in manifest['files']:
        name = safe.relative_file(row['path'])
        if (name != 'dwrite.dll' and not name.startswith('extension/')) or name.casefold() in rows:
            raise ValueError('Seleção CSP inválida')
        if (not re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                or type(row['size_bytes']) is not int or row['size_bytes'] < 0):
            raise ValueError('Metadados CSP inválidos')
        rows[name.casefold()] = row
    if 'dwrite.dll' not in rows:
        raise ValueError('Payload CSP incompleto')
    return {row['path']: row for row in rows.values()}


def _save_receipt(path, data):
    safe.check_components(path)
    if path.exists():
        safe.require_reference(path.lstat(), path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    safe.write_new_json(temporary, data)
    temporary.replace(path)


def _replace(payload, package, manifest, previous, *, pending=None, rollback=True):
    """Troca somente bytes geridos, com backup local e retomada do recibo."""
    record = safe.read_json(package/'prepared.json')
    game = installed.game_path(package, record)
    if record.get('status') != 'prepared' or record.get('content_scope') != 'installed_content':
        raise ValueError('CSP exige jogo completo declarado no pacote')
    expected = next(row['sha256'] for row in record['selection'] if row['relative_path'] == 'acs.exe')
    if digest(game/'acs.exe') != expected:
        raise ValueError('Executável declarado mudou')
    receipt = package/'launcher/csp.json'
    old, new = _managed_rows(previous), _managed_rows(manifest)
    current = {}
    for name in old.keys() | new.keys():
        path = game/name
        safe.check_components(path)
        current[name] = digest(path) if path.exists() else None
        allowed = {row['sha256'] for row in (old.get(name), new.get(name)) if row}
        if current[name] is not None and current[name] not in allowed:
            raise ValueError('Arquivo CSP instalado mudou; preserve-o: '+name)
        if pending is None and name in old and current[name] != old[name]['sha256']:
            raise ValueError('CSP anterior incompleto ou alterado; preserve-o: '+name)
        if pending is None and name not in old and current[name] is not None:
            raise ValueError('Novo destino CSP já existe; preserve-o: '+name)
    if pending is None:
        if rollback:
            backup = package/'launcher/csp-backups'/previous['archive_sha256']
            safe.check_components(backup)
            for name, row in old.items():
                target = backup/name
                safe.check_components(target)
                if target.exists():
                    if digest(target) != row['sha256']:
                        raise ValueError('Backup CSP mudou; preserve-o: '+name)
                else:
                    temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.new')
                    safe.copy_verified(game/name, temporary, row['sha256'])
                    temporary.replace(target)
            if (backup/'manifest.json').exists():
                if safe.read_json(backup/'manifest.json') != previous:
                    raise ValueError('Recibo de backup CSP diverge; preserve-o')
            else:
                _save_receipt(backup/'manifest.json', previous)
        pending = dict(manifest, status='installing', previous=previous,
                       installed_utc=manifest.get('installed_utc', datetime.now(timezone.utc).isoformat()),
                       rollback=previous['archive_sha256'] if rollback else None)
        _save_receipt(receipt, pending)
    # Retira apenas arquivos obsoletos reconhecidos. Mods adicionais ficam intactos.
    for name in old.keys()-new.keys():
        path = game/name
        if current[name] is not None:
            if digest(path) != current[name]:
                raise ValueError('Arquivo CSP mudou durante a atualização: '+name)
            path.unlink()
    # O proxy é o último arquivo substituído, inclusive na retomada.
    for name in sorted(new, key=lambda name: name == 'dwrite.dll'):
        row, path = new[name], game/name
        if current[name] == row['sha256']:
            continue
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
        safe.copy_verified(Path(payload)/name, temporary, row['sha256'])
        safe.check_components(path)
        if (digest(path) if path.exists() else None) != current[name]:
            raise ValueError('Arquivo CSP mudou durante a atualização: '+name)
        temporary.replace(path)
    result = dict(pending, status='ready')
    result.pop('previous')
    if result.get('rollback') is None:
        result.pop('rollback', None)
    _save_receipt(receipt, result)
    return result


def _restore(package):
    package = safe.source_root(package)
    current = safe.read_json(package/'launcher/csp.json')
    pending = current if current.get('status') == 'installing' and current.get('previous') else None
    if pending is not None:
        previous = pending['previous']
        if (current.get('version') != PREVIOUS_VERSION
                or current.get('archive_sha256') != PREVIOUS_ARCHIVE_SHA256):
            raise ValueError('Conclua a atualização CSP antes de reverter')
    else:
        previous = current
        if (current.get('status') != 'ready' or current.get('version') != VERSION
                or current.get('archive_sha256') != ARCHIVE_SHA256
                or current.get('rollback') != PREVIOUS_ARCHIVE_SHA256):
            raise ValueError('Não há backup CSP anterior reconhecido')
    if (previous.get('version') != VERSION or previous.get('archive_sha256') != ARCHIVE_SHA256):
        raise ValueError('Instalação CSP atual desconhecida; preserve o lote')
    backup = package/'launcher/csp-backups'/PREVIOUS_ARCHIVE_SHA256
    manifest = safe.read_json(backup/'manifest.json')
    if (manifest.get('version') != PREVIOUS_VERSION
            or manifest.get('archive_sha256') != PREVIOUS_ARCHIVE_SHA256):
        raise ValueError('Backup CSP anterior desconhecido')
    for name, row in _managed_rows(manifest).items():
        if digest(backup/name) != row['sha256']:
            raise ValueError('Backup CSP mudou; preserve-o: '+name)
    return _replace(backup, package, manifest, previous, pending=pending, rollback=False)


def restore(package):
    """Restaura o CSP anterior gerido com a mesma trava do launcher Linux."""
    package = safe.source_root(package)
    lock = package/'launcher/active.lock'
    safe.check_components(lock)
    if sys.platform != 'linux' or not lock.exists():
        return _restore(package)
    import fcntl
    with lock.open('r+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()), lock)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Close this launcher before restoring CSP') from error
        return _restore(package)


def install(payload, package):
    """Instala/repara o patch e atualiza somente a versão anterior reconhecida."""
    payload, package = Path(payload), safe.source_root(package)
    manifest = verify(payload)
    record = safe.read_json(package/'prepared.json')
    game = installed.game_path(package,record)
    if record.get('status') != 'prepared' or record.get('content_scope') != 'installed_content':
        raise ValueError('CSP exige jogo completo declarado no pacote')
    expected = next(row['sha256'] for row in record['selection'] if row['relative_path'] == 'acs.exe')
    if digest(game/'acs.exe') != expected:
        raise ValueError('Executável declarado mudou')
    receipt = package/'launcher/csp.json'
    safe.check_components(receipt)
    existing_receipt = receipt.exists()
    if existing_receipt:
        data = safe.read_json(receipt)
        if (data.get('status') == 'ready' and data.get('version') == PREVIOUS_VERSION
                and data.get('archive_sha256') == PREVIOUS_ARCHIVE_SHA256):
            return _replace(payload, package, manifest, data)
        if (data.get('status') == 'installing' and data.get('previous')
                and data.get('version') == VERSION and data.get('archive_sha256') == ARCHIVE_SHA256
                and data.get('files') == manifest['files']):
            previous = data['previous']
            if (previous.get('version') != PREVIOUS_VERSION
                    or previous.get('archive_sha256') != PREVIOUS_ARCHIVE_SHA256):
                raise ValueError('Instalação CSP anterior desconhecida; preserve o lote')
            return _replace(payload, package, manifest, previous, pending=data)
        if (data.get('status') not in ('installing', 'ready')
                or data.get('version') != VERSION
                or data.get('archive_sha256') != ARCHIVE_SHA256):
            raise ValueError('Instalação CSP anterior desconhecida ou de outra versão; preserve o lote')
        if data.get('files') != manifest['files']:
            raise ValueError('Seleção CSP diverge do recibo')
    else:
        for name in ('dwrite.dll', 'extension'):
            path = game/name
            safe.check_components(path)
            if path.exists():
                raise ValueError('CSP desconhecido já presente no jogo declarado: '+name)
        data = dict(manifest, status='installing', installed_utc=datetime.now(timezone.utc).isoformat())
    missing = []
    # Conferir todos os arquivos antes de escrever, inclusive na retomada.
    # Um parcial legado no destino final fica preservado e exige intervenção.
    for row in manifest['files']:
        path = game/row['path']
        safe.check_components(path)
        if not path.exists():
            missing.append(row)
        elif digest(path) != row['sha256']:
            raise ValueError('Arquivo CSP instalado mudou; preserve-o: '+row['path'])

    def save_receipt():
        safe.check_components(receipt)
        if receipt.exists():
            safe.require_reference(receipt.lstat(), receipt)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt.with_name('csp-'+uuid.uuid4().hex+'.json')
        safe.write_new_json(temporary, data)
        if not existing_receipt and receipt.exists():
            raise ValueError('Recibo CSP apareceu durante a instalação; preserve-o')
        temporary.replace(receipt)

    if not existing_receipt:
        save_receipt()
        existing_receipt = True
    # Cópia exclusiva em temporário: interrupções não deixam parciais no
    # destino final. O proxy continua por último para impedir carga incompleta.
    for row in sorted(missing, key=lambda row: row['path'] == 'dwrite.dll'):
        path = game/row['path']
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
        safe.copy_verified(payload/row['path'], temporary, row['sha256'])
        safe.check_components(path)
        if path.exists():
            raise ValueError('Destino CSP apareceu durante o reparo; preserve-o')
        temporary.replace(path)
    if data['status'] != 'ready':
        data['status'] = 'ready'
        save_receipt()
    return data


def wine_overrides(value, enabled):
    """Troca só dwrite; conserva as cláusulas de outras DLLs no processo filho."""
    clauses = []
    for clause in value.split(';'):
        if not clause.strip():
            continue
        if '=' not in clause:
            raise ValueError('WINEDLLOVERRIDES tem cláusula inválida')
        names, mode = clause.split('=', 1)
        remaining = [n.strip() for n in names.split(',') if n.strip().lstrip('*').casefold() != 'dwrite']
        if remaining:
            clauses.append(','.join(remaining)+'='+mode)
    clauses.append('dwrite=n,b' if enabled else 'dwrite=b')
    return ';'.join(clauses)


def config_roots(game, environment, explicit=None, *, native_cfg=None):
    """Cobre CUSTOM_PATH e Documents normal, sem presumir que CSP redireciona.

    Documents pode ser um link criado pelo Proton. Resolvemos somente esse
    anchor conhecido; os INIs e descendentes continuam proibindo links.
    """
    game = Path(game)
    own = (Path(native_cfg)/'extension' if native_cfg is not None else
           game/'state/Assetto Corsa/cfg/extension')
    if explicit is not None:
        external = safe.absolute(explicit)
    else:
        external = installed.documents(environment)/'Assetto Corsa/cfg/extension'
    roots = list(dict.fromkeys((safe.absolute(own), external)))
    for root in roots:
        safe.check_components(root)
    return roots


def plan_settings(game, selection, roots, *, weather_style='base'):
    if weather_style not in ('base', 'old_man_linear_inline'):
        raise ValueError('Unknown Weather FX style')
    controls.validate(selection)
    settings = overrides(selection.get('graphics_profile', 'performance'),
                         selection.get('control_mode', 'assisted'),selection.get('ai_behavior','improved'),
                         selection.get('ai_experimental',False))
    enabled=selection.get('smart_shadows', False)
    if type(enabled) is not bool:
        raise ValueError('Smart Shadows must be On or Off')
    settings['smart_shadows.ini']['BASIC']['ENABLED'] = '1' if enabled else '0'
    settings['smart_shadows.ini']['BASIC']['AUTOMATIC_SPLITS_DISTANCE'] = str(graphics.shadow_distance(selection))
    settings['weather_fx.ini']['BASIC']['IMPLEMENTATION'] = weather_style
    comfort.apply_csp(settings, selection)
    chase_camera.apply_csp(settings, selection)
    graphics_settings.apply_csp(settings, selection)
    rows = []
    for index, root in enumerate(roots):
        for name, sections in settings.items():
            path = Path(root)/name
            safe.check_components(path)
            before = None
            if path.exists():
                safe.require_reference(path.lstat(), path)
                before = path.read_bytes()
            ini = parser(before.decode('utf-8-sig') if before else '')
            for section, keys in OBSOLETE_OVERRIDES.get(name, {}).items():
                if section in ini:
                    for key in keys:
                        ini[section].pop(key, None)
                    if not ini[section]:
                        ini.remove_section(section)
            for section, values in sections.items():
                if section not in ini:
                    ini.add_section(section)
                ini[section].update(values)
            stream = io.StringIO()
            ini.write(stream, space_around_delimiters=False)
            rows.append(dict(path=path, previous=before, data=stream.getvalue().encode('utf-8'),
                             name=f'{index}-{name}'))
        # Cor linear permanece desativada, inclusive para seleções antigas.
        # Caminho declarado por __PLUGIN_SETTINGS do CSP selecionado.
        path = Path(root)/f'state/lua/wfx_impl/{weather_style}__settings.ini'
        safe.check_components(path)
        before = None
        if path.exists():
            safe.require_reference(path.lstat(), path)
            before = path.read_bytes()
        ini = parser(before.decode('utf-8-sig') if before else '')
        if 'LINEAR_COLOR_SPACE' not in ini:
            ini.add_section('LINEAR_COLOR_SPACE')
        ini['LINEAR_COLOR_SPACE'].update(ENABLED='0', DEV_MODE='0')
        stream = io.StringIO()
        ini.write(stream, space_around_delimiters=False)
        rows.append(dict(path=path, previous=before, data=stream.getvalue().encode('utf-8'),
                         name=f'{index}-wfx-{weather_style}__settings.ini'))
        for relative, sections in chase_camera.script_settings(selection).items():
            path=Path(root)/relative
            safe.check_components(path)
            before=None
            if path.exists():
                safe.require_reference(path.lstat(),path)
                before=path.read_bytes()
            ini=parser(before.decode('utf-8-sig') if before else '')
            for section,values in sections.items():
                if section not in ini:
                    ini.add_section(section)
                ini[section].update(values)
            stream=io.StringIO()
            ini.write(stream,space_around_delimiters=False)
            rows.append(dict(path=path,previous=before,data=stream.getvalue().encode('utf-8'),
                name=f'{index}-'+relative.replace('/','-')))
    return rows


def write_settings(rows, history):
    """Histórico e substituição atômica de cada INI; não toca defaults do ZIP."""
    history = Path(history)/'csp'
    safe.check_components(history)
    history.mkdir(parents=True, exist_ok=False)
    results = []
    for row in rows:
        path = row['path']
        safe.check_components(path)
        current = path.read_bytes() if path.exists() else None
        if current != row['previous']:
            raise ValueError('Configuração CSP mudou desde a seleção: '+str(path))
    for row in rows:
        path = row['path']
        if row['previous'] is not None:
            (history/('previous-'+row['name'])).write_bytes(row['previous'])
        (history/row['name']).write_bytes(row['data'])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
        with temporary.open('xb') as stream:
            stream.write(row['data'])
        temporary.replace(path)
        results.append(dict(path=str(path), sha256=hashlib.sha256(row['data']).hexdigest(),
                            previously_present=row['previous'] is not None))
    safe.write_new_json(history/'manifest.json', dict(version=VERSION, files=results))
    return results
