"""CSP side proximity indicator, independent of the retired HUD."""
import hashlib
import re
import uuid

from . import driving_haptics_app, file_io as safe, installed

APP_ID = 'ac_deck_proximity_alert'
CONFIG = 'ac_deck_proximity_alert.ini'
DEFAULTS = {'proximity_alert': True, 'proximity_lateral_range': 4, 'proximity_rear_range': 8}
RANGES = {'proximity_lateral_range': (1, 10), 'proximity_rear_range': (1, 20)}
MANIFEST = '''[ABOUT]
NAME = ac-deck Proximity Alert
AUTHOR = ac-deck
VERSION = 1.0
DESCRIPTION = Peripheral indicators for nearby cars.
REQUIRED_VERSION = 3465

[CORE]
LAZY = NONE

[WINDOW_0]
ID = main
NAME = ac-deck Proximity Alert
ICON = icon.png
FUNCTION_MAIN = windowMain
SIZE = 330, 220
'''

SCRIPT = r'''-- Authored proximity cue, not a collision prediction or input controller.
local cfgPath = ac.getFolder(ac.FolderID.ExtCfgUser) .. '/ac_deck_proximity_alert.ini'
local cfg = ac.INIConfig.load(cfgPath)
local enabled = cfg:get('SETTINGS', 'ENABLED', 0) == 1
local function finite(n)
  return type(n) == 'number' and n == n and math.abs(n) < 1000000
end
local function vector(v)
  return v and finite(v.x) and finite(v.y) and finite(v.z)
end
local function dimensions(car)
  local s = car.aabbSize
  if not vector(s) or s.x < 0.5 or s.x > 5 or s.y <= 0 or s.y > 8 or s.z < 1 or s.z > 12 then return nil end
  return s
end
local function dot(a, b)
  return a.x * b.x + a.y * b.y + a.z * b.z
end
local axisX, axisY, axisZ = vec3(1, 0, 0), vec3(0, 1, 0), vec3(0, 0, 1)
local function transformBox(car)
  local body = car.bodyTransform
  return body:transformPoint(car.aabbCenter), body:transformVector(axisX),
    body:transformVector(axisY), body:transformVector(axisZ)
end
local function box(car)
  local size = dimensions(car)
  if not size or not vector(car.aabbCenter) or not car.bodyTransform then return nil end
  local ok, center, x, y, z = pcall(transformBox, car)
  if not ok or not vector(center) or not vector(x) or not vector(y) or not vector(z)
    or dot(x, x) < 0.000001 or dot(y, y) < 0.000001 or dot(z, z) < 0.000001 then return nil end
  return center, x, y, z, size
end
local function extent(axis, x, y, z, size)
  return (size.x * math.abs(dot(x, axis)) + size.y * math.abs(dot(y, axis))
    + size.z * math.abs(dot(z, axis))) / 2
end
local function range(key, default, maximum)
  local value = cfg:get('SETTINGS', key, default)
  if not finite(value) or value < 1 or value > maximum or value ~= math.floor(value) then return default end
  return value
end
local lateralRange = range('LATERAL_RANGE', 4, 10)
local rearRange = range('REAR_RANGE', 8, 20)
local unsaved = false
local function saveRanges()
  local ok = pcall(function()
    cfg:set('SETTINGS', 'ENABLED', enabled and 1 or 0)
    cfg:set('SETTINGS', 'LATERAL_RANGE', lateralRange)
    cfg:set('SETTINGS', 'REAR_RANGE', rearRange)
    cfg:set('SETTINGS', 'EDITED', 1)
    cfg:save(cfgPath)
  end)
  unsaved = not ok
end
local function frame()
  local sim, player = ac.getSim(), ac.getCar(0)
  if not enabled or not sim or not player or not player.physicsAvailable
    or not sim.isSessionStarted or sim.isSessionFinished or sim.isPaused
    or sim.isReplayActive or sim.isInMainMenu or sim.isLookingAtSessionResults
    or not sim.isWindowForeground or sim.focusedCar ~= 0 then return 0, 0, 0, 0 end
  if not vector(player.position) or not vector(player.side) or not vector(player.look)
    or not finite(sim.carsCount) then return 0, 0, 0, 0 end
  if dot(player.side, player.side) < 0.000001 or dot(player.look, player.look) < 0.000001 then return 0, 0, 0, 0 end
  local playerCenter, px, py, pz, playerSize = box(player)
  if not playerCenter then return 0, 0, 0, 0 end
  local playerSideExtent = extent(player.side, px, py, pz, playerSize)
  local playerAlongExtent = extent(player.look, px, py, pz, playerSize)
  local left, right = 0, 0
  local rearLeft, rearRight = 0, 0
  for i = 1, math.min(127, math.floor(sim.carsCount) - 1) do
    local car = ac.getCar(i)
    if car and car.isActive and car.isConnected and vector(car.position) then
      local center, x, y, z, size = box(car)
      if center then
        local dx = center.x - playerCenter.x
        local dy = center.y - playerCenter.y
        local dz = center.z - playerCenter.z
        local side = dx * player.side.x + dy * player.side.y + dz * player.side.z
        local along = dx * player.look.x + dy * player.look.y + dz * player.look.z
        local gap = math.abs(side) - playerSideExtent - extent(player.side, x, y, z, size)
        local alongExtent = playerAlongExtent + extent(player.look, x, y, z, size)
        if math.abs(dy) < 3 and gap < lateralRange then
          if math.abs(along) <= alongExtent then
            local strength = math.max(0, math.min(1, 1 - math.max(0, gap) / lateralRange))
            if side >= 0 then left = math.max(left, strength) end
            if side <= 0 then right = math.max(right, strength) end
          elseif along < -alongExtent and -along - alongExtent < rearRange then
            local strength = 1 - (-along - alongExtent) / rearRange
            if side >= 0 then rearLeft = math.max(rearLeft, strength) end
            if side <= 0 then rearRight = math.max(rearRight, strength) end
          end
        end
      end
    end
  end
  return left, right, rearLeft, rearRight
end
local unregister = ui.onExclusiveHUD(function(mode)
  if mode ~= 'game' then return nil end
  local left, right, rearLeft, rearRight = frame()
  if left <= 0 and right <= 0 and rearLeft <= 0 and rearRight <= 0 then return nil end
  local size = ui.windowSize()
  if not size or size.x <= 0 or size.y <= 0 then return nil end
  local clear = rgbm(0, 0, 0, 0)
  if left > 0 then
    local w = size.x * (0.025 + 0.065 * left)
    local color = rgbm(0, 0, 0, (0.35 + 0.65 * left) * 0.6)
    ui.drawRectFilledMultiColor(vec2(0, 0), vec2(w, size.y), color, clear, clear, color)
  elseif rearLeft > 0 then
    local color = rgbm(0, 0, 0, (0.35 + 0.65 * rearLeft) * 0.6)
    ui.drawRectFilledMultiColor(vec2(0, size.y * 0.78), vec2(size.x * 0.12, size.y), clear, clear, clear, color)
  end
  if right > 0 then
    local w = size.x * (0.025 + 0.065 * right)
    local color = rgbm(0, 0, 0, (0.35 + 0.65 * right) * 0.6)
    ui.drawRectFilledMultiColor(vec2(size.x-w, 0), vec2(size.x, size.y), clear, color, color, clear)
  elseif rearRight > 0 then
    local color = rgbm(0, 0, 0, (0.35 + 0.65 * rearRight) * 0.6)
    ui.drawRectFilledMultiColor(vec2(size.x * 0.88, size.y * 0.78), vec2(size.x, size.y), clear, clear, color, clear)
  end
  return nil
end, true)
ac.onRelease(function() if type(unregister) == 'function' then unregister() end end)
function script.windowMain()
  local enabledChanged = ui.checkbox('Proximity alert', enabled)
  if enabledChanged then enabled = not enabled end
  local lateral, lateralChanged = ui.slider('##sideRange', lateralRange, 1, 10, 'Side detection: %.0f m', true)
  local rear, rearChanged = ui.slider('##rearRange', rearRange, 1, 20, 'Rear detection: %.0f m', true)
  if enabledChanged or lateralChanged or rearChanged then
    if finite(lateral) then lateralRange = math.max(1, math.min(10, math.floor(lateral + 0.5))) end
    if finite(rear) then rearRange = math.max(1, math.min(20, math.floor(rear + 0.5))) end
    saveRanges()
  end
  ui.textWrapped('Side distance also limits cars behind. Changes apply immediately.')
  if unsaved then
    ui.textWrapped('Could not save settings. Changes apply only for this session.')
    if ui.button('Retry save') then saveRanges() end
  end
end
'''


def validate(selection):
    if type(selection.get('proximity_alert', True)) is not bool:
        raise ValueError('Proximity alert must be On or Off')
    for key, (minimum, maximum) in RANGES.items():
        value = selection.get(key, DEFAULTS[key])
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'{key} must be a whole number between {minimum} and {maximum} metres')


def install(package):
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder, receipt = game/'apps/lua'/APP_ID, package/'launcher/proximity-alert-app.json'
    for path in (folder, receipt): safe.check_components(path)
    assets = {'manifest.ini': MANIFEST.encode(), APP_ID+'.lua': SCRIPT.encode(),
              'icon.png': driving_haptics_app.icon()}
    files = {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()}
    old = {}
    if receipt.exists():
        old = safe.read_json(receipt)
        if not isinstance(old, dict):
            raise ValueError('Proximity alert receipt differs; preserve installed files')
        internal = package/'game'
        moved = (isinstance(old.get('folder'), str) and folder.is_relative_to(internal)
                 and old['folder'].endswith('/game/'+folder.relative_to(internal).as_posix()))
        if (old.get('revision') != 1 or (old.get('folder') != str(folder) and not moved)
                or not isinstance(old.get('files'), dict) or set(old['files']) != set(files)
                or not isinstance(old.get('previous_files', {}), dict)
                or any(not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value)
                       for value in (*old['files'].values(), *old.get('previous_files', {}).values()))):
            raise ValueError('Proximity alert receipt differs; preserve installed files')
    elif folder.exists():
        raise ValueError('Unknown proximity alert app; preserve installed files')
    for name, expected in files.items():
        path = folder/name
        safe.check_components(path)
        if path.exists() and safe.hash_reference_file(path)[0] not in {
                expected, old.get('files', {}).get(name), old.get('previous_files', {}).get(name)}:
            raise ValueError('Proximity alert app was modified; preserve it')
    record = dict(schema_version=1, revision=1, folder=str(folder), files=files,
                  previous_files=old.get('previous_files', old.get('files', {})), status='installing')
    def save():
        receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt.with_name('proximity-alert-'+uuid.uuid4().hex+'.json')
        safe.write_new_json(temporary, record)
        temporary.replace(receipt)
    save()
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        path = folder/name
        if not path.exists() or safe.hash_reference_file(path)[0] != files[name]:
            temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
            with temporary.open('xb') as stream: stream.write(data)
            temporary.replace(path)
    record['status'] = 'ready'
    record.pop('previous_files')
    save()
    return record
