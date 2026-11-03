"""Installed CSP gamepad scripts and optional Advanced Gamepad Assist settings.

The AGA bridge targets the shared interface of version 1.5.5. It does not
modify the third-party script or assume an undocumented ac.storage format.
"""
import configparser
import hashlib
from pathlib import Path
import uuid

from . import file_io as safe
from . import installed, driving_haptics_app

DEFAULT_SCRIPT = 'gamepad_force'
AGA = 'Advanced Gamepad Assist'
AGA_VERSION = '1.5.5'
APP_ID = 'ac_deck_aga_settings'
CONFIG = 'ac_deck_aga.ini'
SNAPSHOT = 'ac_deck_aga_observed.ini'

# Reset flags written by the previous bridge, even if its app is still installed.
LEGACY_FIELDS = ('useFilter', 'filterSetting', 'steeringRate', 'rateIncreaseWithSpeed',
                 'targetSlip', 'countersteerResponse', 'maxDynamicLimitReduction',
                 'selfSteerResponse', 'maxSelfSteerAngle', 'dampingStrength')
DEFAULTS = {'gamepad_script': DEFAULT_SCRIPT, 'aga_enabled': 'keep'}
KEYS = ('gamepad_script', 'aga_enabled')


def valid_id(value):
    if not isinstance(value, str) or not value or len(value) > 128 or value.strip() != value:
        return False
    if any(not ch.isprintable() or ch in '/\\[];=#' for ch in value):
        return False
    try:
        return safe.relative_file(value) == value
    except (ValueError, RuntimeError):
        return False


def scripts(game):
    """List safe installed scripts, retaining the built-in default before installation."""
    result = {DEFAULT_SCRIPT: 'Gamepad Force'}
    if game is None:
        return result
    root = Path(game)/'extension/lua/joypad-assist'
    try:
        safe.check_components(root)
        if not root.is_dir():
            return result
        for folder in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
            if not valid_id(folder.name):
                continue
            try:
                safe.check_components(folder/'assist.lua')
                safe.require_reference((folder/'assist.lua').lstat(), folder/'assist.lua')
                label = folder.name
                manifest = folder/'manifest.ini'
                if manifest.exists():
                    safe.check_components(manifest)
                    safe.require_reference(manifest.lstat(), manifest)
                    ini = configparser.ConfigParser(interpolation=None, strict=False)
                    ini.read_string(manifest.read_text('utf-8-sig'))
                    candidate = ini.get('ABOUT', 'NAME', fallback=label).strip()
                    if candidate and len(candidate) <= 80 and all(ch.isprintable() for ch in candidate):
                        label = candidate
                result[folder.name] = label
            except (OSError, UnicodeError, configparser.Error, ValueError, RuntimeError):
                continue
    except (OSError, ValueError, RuntimeError):
        pass
    return result


def validate(selection):
    script = selection.get('gamepad_script', DEFAULT_SCRIPT)
    if not valid_id(script):
        raise ValueError('Invalid Gamepad FX script name')
    if selection.get('aga_enabled', 'keep') not in ('keep', 'on', 'off'):
        raise ValueError('Invalid Advanced Gamepad Assist switch')


def values(selection):
    """Values written to the bridge; unselected mod settings remain untouched."""
    validate(selection)
    result = {}
    enabled = selection.get('aga_enabled', 'keep')
    if enabled != 'keep':
        result['assistEnabled'] = 1 if enabled == 'on' else 0
    return result


def require_installed(game, selection):
    validate(selection)
    script = selection.get('gamepad_script', DEFAULT_SCRIPT)
    if selection.get('control_mode', 'assisted') != 'assisted' or script == DEFAULT_SCRIPT:
        return
    if script not in scripts(game):
        raise ValueError('Selected Gamepad FX script is not installed: '+script)
    if script == AGA and values(selection) and not supported(game):
        raise ValueError('AGA settings require version '+AGA_VERSION+'; leave the mod settings unchanged for other versions')


def supported(game):
    manifest = Path(game)/'extension/lua/joypad-assist'/AGA/'manifest.ini'
    try:
        safe.check_components(manifest)
        safe.require_reference(manifest.lstat(), manifest)
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(manifest.read_text('utf-8-sig'))
        return ini.get('ABOUT', 'VERSION', fallback='').strip() == AGA_VERSION
    except (OSError, UnicodeError, configparser.Error, ValueError, RuntimeError):
        return False


def bridge_section(selection):
    selected = (selection.get('control_mode', 'assisted') == 'assisted'
                and selection.get('gamepad_script', DEFAULT_SCRIPT) == AGA)
    current = values(selection) if selected else {}
    result = {'ENABLED': '1' if current else '0'}
    for field in ('assistEnabled', *LEGACY_FIELDS):
        result[field.upper()+'_SET'] = '1' if field in current else '0'
        if field in current:
            result[field.upper()] = str(current[field])
    return {'SETTINGS': result}


MANIFEST = '''[ABOUT]
NAME = ac-deck Gamepad Settings
AUTHOR = ac-deck
VERSION = 1.0
DESCRIPTION = Applies selected Advanced Gamepad Assist settings once at session start.
REQUIRED_VERSION = 3465

[CORE]
LAZY = NONE

[WINDOW_0]
ID = main
NAME = ac-deck Gamepad Settings
ICON = icon.png
FUNCTION_MAIN = windowMain
SIZE = 360, 100
'''

# Layout and readiness signal follow AGA 1.5.5's own UI application.
SCRIPT = r'''local data = ac.connect{
  ac.StructItem.key('AGAData'),
  _appCanRun=ac.StructItem.boolean(),
  _rAxleHVelAngle=ac.StructItem.double(), _selfSteerStrength=ac.StructItem.double(),
  _frontNdSlip=ac.StructItem.double(), _rearNdSlip=ac.StructItem.double(),
  _maxLimitReduction=ac.StructItem.double(), _limitReduction=ac.StructItem.double(),
  _gameGamma=ac.StructItem.double(), _gameDeadzone=ac.StructItem.double(),
  _gameRumble=ac.StructItem.double(), _rawSteer=ac.StructItem.double(),
  _finalSteer=ac.StructItem.double(), assistEnabled=ac.StructItem.boolean(),
  graphSelection=ac.StructItem.int32(), keyboardMode=ac.StructItem.int32(),
  autoClutch=ac.StructItem.boolean(), autoShiftingMode=ac.StructItem.int32(),
  autoShiftingCruise=ac.StructItem.boolean(), autoShiftingDownBias=ac.StructItem.double(),
  triggerFeedbackL=ac.StructItem.double(), triggerFeedbackR=ac.StructItem.double(),
  triggerFeedbackAlwaysOn=ac.StructItem.boolean(), useFilter=ac.StructItem.boolean(),
  filterSetting=ac.StructItem.double(), steeringRate=ac.StructItem.double(),
  targetSlip=ac.StructItem.double(), rateIncreaseWithSpeed=ac.StructItem.double(),
  selfSteerResponse=ac.StructItem.double(), dampingStrength=ac.StructItem.double(),
  maxSelfSteerAngle=ac.StructItem.double(), countersteerResponse=ac.StructItem.double(),
  maxDynamicLimitReduction=ac.StructItem.double(), photoMode=ac.StructItem.boolean()
}
local root = ac.getFolder(ac.FolderID.ExtCfgUser)
local cfg = ac.INIConfig.load(root .. '\\ac_deck_aga.ini')
local fx = ac.INIConfig.load(root .. '\\gamepad_fx.ini')
local mod = ac.INIConfig.load(ac.getFolder(ac.FolderID.ExtLua) .. '\\joypad-assist\\Advanced Gamepad Assist\\manifest.ini')
local active = mod:get('ABOUT', 'VERSION', '') == '1.5.5'
  and fx:get('BASIC', 'ENABLED', 0) == 1
  and fx:get('JOYPAD_ASSIST', 'ENABLED', 0) == 1
  and fx:get('JOYPAD_ASSIST', 'IMPLEMENTATION', '') == 'Advanced Gamepad Assist'
local apply = cfg:get('SETTINGS', 'ENABLED', 0) == 1
local done = false
local snapshotPath = root .. '\\ac_deck_aga_observed.ini'
local elapsed = 1
local previous = nil
local function observe()
  local fields = {'assistEnabled'}
  local values = {}
  for i, field in ipairs(fields) do
    local value = data[field]
    values[i] = type(value) == 'boolean' and (value and 1 or 0) or value
  end
  local stamp = table.concat(values, '|')
  if stamp == previous then return end
  local ok, written = pcall(function()
    local observed = ac.INIConfig.load(snapshotPath)
    if io.fileExists(snapshotPath) and observed:get('AGA', 'OWNER', '') ~= 'ac-deck' then return false end
    observed:set('AGA', 'OWNER', 'ac-deck')
    observed:set('AGA', 'VERSION', '1.5.5')
    for i, field in ipairs(fields) do observed:set('AGA', string.upper(field), values[i]) end
    observed:save(snapshotPath)
    return true
  end)
  if ok and written then previous = stamp end
end
function script.update(dt)
  if not active or not data._appCanRun then return end
  if not done and apply and cfg:get('SETTINGS', 'ASSISTENABLED_SET', 0) == 1 then
    local value = cfg:get('SETTINGS', 'ASSISTENABLED', -1)
    if value == 0 or value == 1 then data.assistEnabled = value == 1 end
  end
  done = true
  elapsed = elapsed + dt
  if elapsed >= 1 then elapsed = 0; observe() end
end
ac.onRelease(function() if active and data._appCanRun then observe() end end)
function script.windowMain()
  ui.textWrapped(done and 'Launcher settings applied for this session.' or 'Waiting for Advanced Gamepad Assist.')
end
'''


def install(package):
    """Install only our own bridge, preserving unknown or modified files."""
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder = game/'apps/lua'/APP_ID
    receipt = package/'launcher/aga-settings-app.json'
    for path in (folder, receipt):
        safe.check_components(path)
    assets = {'manifest.ini': MANIFEST.encode(), APP_ID+'.lua': SCRIPT.encode(),
              'icon.png': driving_haptics_app.icon()}
    files = {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()}
    old = {}
    if receipt.exists():
        old = safe.read_json(receipt)
        internal = package/'game'
        moved = (isinstance(old.get('folder'), str) and folder.is_relative_to(internal)
                 and old['folder'].endswith('/game/'+folder.relative_to(internal).as_posix()))
        if (old.get('revision') != 1 or (old.get('folder') != str(folder) and not moved)
                or not isinstance(old.get('files'), dict) or set(old['files']) != set(files)
                or not isinstance(old.get('previous_files', {}), dict)):
            raise ValueError('AGA settings app receipt differs; preserve installed files')
    elif folder.exists():
        raise ValueError('Unknown AGA settings app; preserve installed files')
    for name, expected in files.items():
        path = folder/name
        safe.check_components(path)
        if path.exists() and safe.hash_reference_file(path)[0] not in {
                expected, old.get('files', {}).get(name), old.get('previous_files', {}).get(name)}:
            raise ValueError('AGA settings app was modified; preserve it')
    record = dict(schema_version=1, revision=1, folder=str(folder), files=files,
                  previous_files=old.get('previous_files', old.get('files', {})), status='installing')
    def save():
        receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt.with_name('aga-settings-'+uuid.uuid4().hex+'.json')
        safe.write_new_json(temporary, record)
        temporary.replace(receipt)
    save()
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        path = folder/name
        if not path.exists() or safe.hash_reference_file(path)[0] != files[name]:
            temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
            with temporary.open('xb') as stream:
                stream.write(data)
            temporary.replace(path)
    record['status'] = 'ready'
    record.pop('previous_files')
    save()
    return record
