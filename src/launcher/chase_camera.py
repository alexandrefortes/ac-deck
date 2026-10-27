"""Seleção da câmera CSP distribuída, sem alterar scripts ou os controles.

Conferido em CSP 0.2.11: extension/config/chaser_camera.ini e os quatro
scripts em extension/lua/chaser-camera. O seletor aplica a mesma câmera
às duas vistas de perseguição. Não muda a vista inicial da sessão.

O script autoral usa ac.INIConfig.scriptSettings(). GT5 e BACC pessoais têm
adaptadores separados para distância/altura/pitch, sem alterar suas rotinas
de FOV ou o chase_cam.ini nativo. Uso real depende de conferência no Deck.
"""
import hashlib
import math
import os
from pathlib import Path
import sys
import uuid

from . import file_io as safe

SCRIPT = 'old_man_adjustable'
GT5 = 'spec 2.0'
BACC_UNBOUND = 'BACC - NFS Unbound'
BACC_GT = 'BACC - GT'
BACC = (BACC_UNBOUND, BACC_GT)
VERIFIED_CSP_VERSION = '0.2.11'

MODES = {
    'original': 'Original',
    SCRIPT: 'CSP Adjustable',
    GT5: 'GT5 Spec 2.0',
    'base': 'CSP Basic',
    'arcade-mode': 'CSP Arcade',
    'arcade-mode-2': 'CSP Arcade 2',
    'drone': 'CSP Drone',
    BACC_UNBOUND: 'BACC - NFS Unbound',
    BACC_GT: 'BACC - GT',
}
LOOK = {'right': 'Right stick', 'disabled': 'Disabled'}
DEADZONES = (0.03, 0.05, 0.1, 0.15, 0.2)
EXPONENTS = (1, 1.4, 1.8, 2.2, 3)
DEFAULTS = dict(chase_camera='original', chase_look='right',
                chase_deadzone=0.03, chase_exponent=1.8,
                chase_distance=5.7, chase_height=1.6, chase_pitch=0, chase_fov=60)
SETTINGS = {
    'chase_camera': 'Chase camera (CSP)',
    'chase_look': 'Chase camera look (CSP)',
    'chase_deadzone': 'Chase look deadzone (CSP)',
    'chase_exponent': 'Chase look exponent (CSP)',
    'chase_distance': 'Chase distance, both views (m)',
    'chase_height': 'Chase height, both views (m)',
    'chase_pitch': 'Chase pitch offset (degrees)',
    'chase_fov': 'Chase field of view (degrees)',
}
RANGES = {'chase_distance': (3, 8, 0.1), 'chase_height': (0.5, 3, 0.1),
          'chase_pitch': (-15, 15, 1), 'chase_fov': (40, 100, 5)}
FIELDS = {'chase_distance': 'DISTANCE', 'chase_height': 'HEIGHT',
          'chase_pitch': 'PITCH', 'chase_fov': 'FOV'}
CHOICES = {'chase_camera': MODES, 'chase_look': LOOK,
           'chase_deadzone': DEADZONES, 'chase_exponent': EXPONENTS}
for _key, (_low, _high, _step) in RANGES.items():
    CHOICES[_key] = tuple(round(_low + n * _step, 5)
                          for n in range(round((_high - _low) / _step) + 1))

# Apenas APIs presentes no SDK ac_chaser_camera do CSP 0.2.11. A posição é
# relativa à origem do carro, não uma altura garantida sobre o asfalto.
# O pitch é um deslocamento da direção que mira 1 m acima dessa origem.
CAMERA_LUA = '''-- Old Man Assetto Corsa: adjustable chase camera, both chase views.
local cfg = ac.INIConfig.scriptSettings():mapSection('SETTINGS', {
  DISTANCE = 5.7, HEIGHT = 1.6, PITCH = 0, FOV = 60
})
local look = smoothing(0, 10)

function script.update(dt, cameraIndex)
  smoothing.setDT(dt)
  local stick = ac.getJoystickLook()
  local target = 0
  if ac.looksBehind() or (ac.looksLeft() and ac.looksRight()) then
    target = 1
  elseif ac.looksLeft() then
    target = 0.5
  elseif ac.looksRight() then
    target = -0.5
  elseif stick ~= nil then
    target = stick.x
  end
  look:update(target)

  local pos = ac.getCarPosition()
  local forward = ac.getCarDirection()
  local carUp = ac.getCarUp()
  local right = math.cross(forward, carUp):normalize()
  local angle = look.val * math.pi
  local distance = math.clamp(cfg.DISTANCE, 3, 8)
  local height = math.clamp(cfg.HEIGHT, 0.5, 3)
  ac.Camera.position = pos + (right * math.sin(angle) - forward * math.cos(angle)) * distance
    + vec3(0, height, 0)
  local direction = (pos + vec3(0, 1, 0) - ac.Camera.position):normalize()
  local pitchAxis = math.cross(direction, vec3(0, 1, 0)):normalize()
  direction:rotate(quat.fromAngleAxis(math.radians(math.clamp(cfg.PITCH, -15, 15)), pitchAxis))
  ac.Camera.direction = direction
  ac.Camera.up = vec3(0, 1, 0)
  ac.Camera.fov = math.clamp(cfg.FOV, 40, 100)
end
'''
MANIFEST_INI = '''[ABOUT]
NAME = Old Man - Adjustable chase camera
AUTHOR = Old Man Assetto Corsa
VERSION = 1.0
DESCRIPTION = Stable chase camera. Distance, height, pitch offset and field of view apply to both chase views. Verified APIs: CSP 0.2.11; Deck validation pending.
'''
SETTINGS_INI = '''[SETTINGS]
DISTANCE = 5.7 ; Both chase views distance; from 3 m to 8, round to 0.1
HEIGHT = 1.6 ; Both chase views height from car origin; from 0.5 m to 3, round to 0.1
PITCH = 0 ; Pitch offset from looking at car; from -15 degrees to 15, round to 1
FOV = 60 ; Field of view; from 40 degrees to 100, round to 5
'''


def validate(selection):
    """Valida somente os campos presentes, antes de alterar o plano de INIs."""
    for key, choices in (('chase_camera', MODES), ('chase_look', LOOK)):
        if key in selection and (type(selection[key]) is not str or selection[key] not in choices):
            raise ValueError('Unknown chase camera setting: '+key)
    for key, choices in (('chase_deadzone', DEADZONES), ('chase_exponent', EXPONENTS)):
        if key in selection:
            value = selection[key]
            if type(value) not in (int, float) or value not in choices:
                raise ValueError('Unsupported chase camera value: '+key)
    for key, (low, high, step) in ranges(selection.get('chase_camera')).items():
        if key in selection:
            value = selection[key]
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not low <= value <= high
                    or abs((value-low)/step - round((value-low)/step)) > 1e-8):
                raise ValueError('Unsupported adjustable camera value: '+key)
    if 'chase_presets' in selection:
        bank = selection['chase_presets']
        if not isinstance(bank, dict) or len(bank) > len(MODES):
            raise ValueError('Invalid chase camera presets')
        for mode, values in bank.items():
            if mode not in MODES or not isinstance(values, dict) or set(values) != set(GEOMETRY):
                raise ValueError('Invalid chase camera preset')
            validate(dict(values, chase_camera=mode))


GEOMETRY = ('chase_distance', 'chase_height', 'chase_pitch')


def ranges(mode):
    result = dict(RANGES)
    if mode in BACC:
        result.update(chase_distance=(2.8, 8, 0.1), chase_pitch=(-15, 15, 0.1))
    return result


def geometry_defaults(mode):
    return (dict(chase_distance=2.8, chase_height=1.3, chase_pitch=3.4)
            if mode in BACC else {key: DEFAULTS[key] for key in GEOMETRY})


def choices(selection):
    result = dict(CHOICES)
    for key, (low, high, step) in ranges(selection.get('chase_camera')).items():
        result[key] = tuple(round(low+n*step, 5) for n in range(round((high-low)/step)+1))
    return result


def switch_style(selection, mode):
    """Guarda a geometria atual e restaura a do destino; não altera direção/FOV."""
    validate(selection)
    if type(mode) is not str or mode not in MODES:
        raise ValueError('Unknown chase camera style')
    current = selection.get('chase_camera', DEFAULTS['chase_camera'])
    if current == mode:
        return
    bank = {key: dict(value) for key, value in selection.get('chase_presets', {}).items()}
    defaults = geometry_defaults(current)
    if 'chase_presets' not in selection and current not in BACC:
        # Antes da 036 todos os estilos antigos compartilhavam estes campos.
        # Conservar a preferência herdada; apenas os BACC novos usam 2.8/1.3/3.4.
        legacy = {key: selection.get(key, defaults[key]) for key in GEOMETRY}
        bank = {old: dict(legacy) for old in MODES if old not in BACC}
    bank[current] = {key: selection.get(key, defaults[key]) for key in GEOMETRY}
    destination = bank.get(mode, geometry_defaults(mode))
    candidate = dict(selection, **destination, chase_camera=mode, chase_presets=bank)
    validate(candidate)
    selection.update(candidate)


def apply_csp(settings, selection):
    """Mescla overrides no plano existente; a escrita e reversão cabem ao CSP."""
    validate(selection)

    def put(section, **values):
        settings.setdefault('chaser_camera.ini', {}).setdefault(section, {}).update(values)

    if 'chase_camera' in selection:
        mode = selection['chase_camera']
        for section in ('BASIC', 'BASIC_2'):
            put(section, ENABLED='0' if mode == 'original' else '1')
            if mode != 'original':
                put(section, IMPLEMENTATION=mode)
    if 'chase_look' in selection:
        put('LOOK', XBOX_STICK='1' if selection['chase_look'] == 'right' else '-1')
    if 'chase_deadzone' in selection:
        put('LOOK', XBOX_STICK_DEADZONE=format(selection['chase_deadzone'], '.2f'))
    if 'chase_exponent' in selection:
        put('LOOK', XBOX_STICK_EXPONENT=format(selection['chase_exponent'], '.2f'))


def script_settings(selection):
    """Overrides relativos à raiz cfg/extension, um por vista real do CSP.

    __PLUGIN_SETTINGS do módulo declara as duas áreas abaixo. O chamador
    deve juntá-las ao histórico com nomes de arquivo sem barras, como faz
    para wfx_impl; não tratar estes caminhos como novos defaults do ZIP.
    """
    validate(selection)
    mode = selection.get('chase_camera')
    if mode not in (SCRIPT, GT5, *BACC):
        return {}
    defaults = dict(DEFAULTS, **geometry_defaults(mode))
    values = {field: format(selection.get(key, defaults[key]), '.2f')
              for key, field in FIELDS.items() if mode == SCRIPT or key != 'chase_fov'}
    return {f'state/lua/{folder}/{mode}__settings.ini': {'SETTINGS': dict(values)}
            for folder in ('chaser_camera', 'chaser_camera_2')}


def assets():
    """Três arquivos autorais para uma pasta nova de implementação CSP."""
    return [dict(path=name, data=raw.encode('utf-8'),
                 sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest())
            for name, raw in (('camera.lua', CAMERA_LUA), ('settings.ini', SETTINGS_INI),
                              ('manifest.ini', MANIFEST_INI))]


def _digest(path):
    return safe.hash_reference_file(Path(path))[0]


def _context(package):
    from . import installed
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder = game/'extension/lua/chaser-camera'/SCRIPT
    receipt = package/'launcher/chase-camera.json'
    safe.check_components(folder)
    safe.check_components(receipt)
    return folder, receipt


def _expected(folder, rows):
    return dict(schema_version=1, implementation=SCRIPT, csp_version=VERIFIED_CSP_VERSION,
                folder=str(folder), files=[dict(path=r['path'], sha256=r['sha256']) for r in rows])


def _read(receipt, expected):
    data = safe.read_json(receipt)
    folder = Path(expected['folder'])
    internal = receipt.parent.parent/'game'
    moved = (folder.is_relative_to(internal) and isinstance(data.get('folder'), str)
             and data['folder'].endswith('/game/'+folder.relative_to(internal).as_posix()))
    if (any(data.get(key) != value for key, value in expected.items() if key != 'folder')
            or (data.get('folder') != str(folder) and not moved)):
        raise ValueError('Chase camera receipt does not match this package/script')
    if data.get('status') not in ('installing', 'ready', 'restored'):
        raise ValueError('Invalid chase camera receipt status')
    return data


def _save(receipt, data):
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_name('chase-camera-'+uuid.uuid4().hex+'.json')
    safe.write_new_json(temporary, data)
    temporary.replace(receipt)


def install(package):
    """Adicionar apenas a pasta autoral; chamar sob a trava de lançamento."""
    rows = assets()
    folder, receipt = _context(package)
    expected = _expected(folder, rows)
    if receipt.exists():
        previous = _read(receipt, expected)
        if previous['status'] == 'ready':
            missing = []
            for row in rows:
                path = folder/row['path']
                safe.check_components(path)
                if not path.exists():
                    missing.append(row)
                elif _digest(path) != row['sha256']:
                    raise ValueError('Managed chase camera changed: '+row['path'])
            for row in missing:
                path = folder/row['path']
                folder.mkdir(parents=True, exist_ok=True)
                temporary = folder/(row['path']+'.'+uuid.uuid4().hex+'.new')
                with temporary.open('xb') as stream:
                    stream.write(row['data'])
                if _digest(temporary) != row['sha256']:
                    raise ValueError('Chase camera temporary copy changed')
                safe.check_components(path)
                if path.exists():
                    raise ValueError('Chase camera destination appeared during repair')
                temporary.replace(path)
            if previous['folder'] != str(folder):
                previous['folder'] = str(folder)
                _save(receipt, previous)
            return previous
        if previous['status'] != 'restored':
            raise ValueError('Interrupted chase camera install; restore before retrying')
    if folder.exists():
        raise ValueError('Chase camera directory already exists; preserve it')
    data = dict(expected, status='installing')
    _save(receipt, data)
    folder.mkdir(parents=True)
    for row in rows:
        path = folder/row['path']
        safe.check_components(path)
        with path.open('xb') as stream:
            stream.write(row['data'])
        if _digest(path) != row['sha256']:
            raise ValueError('Chase camera copy changed: '+row['path'])
    data['status'] = 'ready'
    _save(receipt, data)
    return data


def _restore(package):
    rows = assets()
    folder, receipt = _context(package)
    data = _read(receipt, _expected(folder, rows))
    if data['status'] == 'restored':
        return data
    present = []
    for row in rows:
        path = folder/row['path']
        safe.check_components(path)
        if path.exists():
            if _digest(path) != row['sha256']:
                raise ValueError('Managed chase camera changed; nothing removed: '+row['path'])
            present.append((path, row['sha256']))
    for path, expected_hash in present:
        if _digest(path) != expected_hash:
            raise ValueError('Chase camera changed during restoration')
        path.unlink()
    if folder.exists() and not any(folder.iterdir()):
        folder.rmdir()
    data.update(status='restored', folder=str(folder))
    _save(receipt, data)
    return data


def restore(package):
    """Jogo/menu fechados. Preservar arquivos estranhos e originais do CSP."""
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
            raise ValueError('Close this launcher before restoring its chase camera') from error
        return _restore(package)
