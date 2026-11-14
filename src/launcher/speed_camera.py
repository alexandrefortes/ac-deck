"""Câmera de perseguição autoral para o CSP 0.3.0."""

SCRIPT = 'ac_deck_speed'
CSP_VERSION = '0.3.0'
GEOMETRY = dict(chase_distance=5.0, chase_height=1.4, chase_pitch=0)

CAMERA_LUA = '''local cfg = ac.INIConfig.scriptSettings():mapSection('SETTINGS', {
  DISTANCE = 5.0, HEIGHT = 1.4, PITCH = 0
})
local worldUp = vec3(0, 1, 0)
local speedBlend, look

function script.onCarChanged()
  speedBlend, look = nil, nil
end

function script.update(dt, cameraIndex)
  local far = cameraIndex == 2
  local t = math.clamp((car.speedKmh - 70) / 170, 0, 1)
  local speedTarget = t * t * (3 - 2 * t)

  local left, right = ac.looksLeft(), ac.looksRight()
  local stick = ac.getJoystickLook()
  local lookTarget = 0
  if ac.looksBehind() or (left and right) then
    lookTarget = look and look < 0 and -1 or 1
  elseif left then
    lookTarget = 0.5
  elseif right then
    lookTarget = -0.5
  elseif stick ~= nil then
    lookTarget = math.clamp(stick.x, -1, 1)
  end

  if speedBlend == nil or dt > 0.25 then
    speedBlend, look = speedTarget, lookTarget
  elseif dt > 0 then
    speedBlend = speedBlend + (speedTarget - speedBlend) * (1 - math.exp(-dt / 0.35))
    look = look + (lookTarget - look) * (1 - math.exp(-dt / 0.1))
  end

  local forward = car.look
  local side = math.cross(forward, car.up):normalize()
  local angle = look * math.pi
  local distance = math.clamp(cfg.DISTANCE, 3, 8) + (far and 0.75 or 0) + 0.16 * speedBlend
  local height = math.clamp(cfg.HEIGHT, 0.5, 3) + (far and 0.15 or 0)
  local position = car.position + (side * math.sin(angle) - forward * math.cos(angle)) * distance
    + worldUp * height
  local aim = car.position + forward * (1.6 * (1 - math.abs(look))) + worldUp * 0.95
  local direction = (aim - position):normalize()
  local pitchAxis = math.cross(direction, worldUp)
  if pitchAxis:lengthSquared() < 0.000001 then
    pitchAxis = math.cross(direction, side)
  end
  pitchAxis:normalize()
  local up = math.cross(pitchAxis, direction)
  local pitch = math.rad(math.clamp(cfg.PITCH, -15, 15))
  direction = direction * math.cos(pitch) + up * math.sin(pitch)

  ac.Camera.position = position
  ac.Camera.direction = direction
  ac.Camera.up = math.cross(pitchAxis, direction)
  ac.Camera.fov = (far and 52 or 50) + 8 * speedBlend
end
'''

SETTINGS_INI = '''[SETTINGS]
DISTANCE = 5.0 ; Near chase distance in meters
HEIGHT = 1.4 ; Near chase height from car origin in meters
PITCH = 0 ; Pitch offset in degrees
'''

MANIFEST_INI = '''[ABOUT]
NAME = ac-deck Speed Chase
AUTHOR = ac-deck
VERSION = 1.0
DESCRIPTION = Chase camera with a progressive field of view and a small speed-dependent setback.
'''
