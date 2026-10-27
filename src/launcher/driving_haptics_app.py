"""App autoral CSP: lê o carro do jogador, envia somente sinais numéricos locais."""
import hashlib
from pathlib import Path
import struct
import uuid
import zlib

from . import file_io as safe
from . import installed

APP_ID = 'old_man_driving_haptics'
MANIFEST = '''[ABOUT]
NAME = Old Man Driving Haptics
AUTHOR = Old Man Assetto Corsa
VERSION = 0.1
DESCRIPTION = Local driving feedback for Steam Deck. Brake left, throttle right. Steering and inputs remain unchanged.
REQUIRED_VERSION = 3465

[CORE]
LAZY = NONE

[WINDOW_0]
ID = main
NAME = Old Man Driving Haptics
ICON = icon.png
FUNCTION_MAIN = windowMain
SIZE = 330, 110
'''
SCRIPT = r'''-- Old Man Assetto Corsa: telemetry only. No input or physics writes.
local socket = require('shared/socket')
local endpoint = io.load(require('old_man_paths')) or ''
local port, token = endpoint:match('^(%d+)\n([a-f0-9]+)\n$')
port = tonumber(port)
local udp = port and #token == 32 and socket.udp() or nil
if udp then udp:settimeout(0) end
local elapsed, sequence = 0, 0
local status = udp and 'Ready. Feedback follows the driving session.' or 'Driving haptics are off for this session.'
local function number(value)
  value = tonumber(value) or 0
  if value ~= value or math.abs(value) > 1e12 then value = 0 end
  return string.format('%.6f', value)
end
function script.update(dt)
  if not udp then return end
  elapsed = elapsed + dt
  if elapsed < 0.02 then return end
  elapsed = 0
  local car, sim = ac.getCar(0), ac.getSim()
  if not car then return end
  sequence = sequence + 1
  local active = car.physicsAvailable and not sim.isPaused and not sim.isInMainMenu and not sim.isReplayActive
  local values = {'OMH1', token, tostring(sequence), active and '1' or '0'}
  local function add(value) values[#values+1] = number(value) end
  add(car.timestamp); add(car.speedKmh); add(car.gas); add(car.brake)
  add(car.gear); add(car.rpm); add(car.rpmLimiter)
  add(car.steerLock > 0 and car.steer / car.steerLock or 0)
  add(car.absInAction and 1 or 0); add(car.tractionControlInAction and 1 or 0)
  add(car.tractionType)
  for _, key in ipairs({'slipRatio', 'slipAngle', 'angularSpeed', 'tyreRadius', 'suspensionTravel', 'surfaceVibrationGain'}) do
    for i = 0, 3 do add(car.wheels[i][key]) end
  end
  for i = 0, 4 do add(car.damage[i]) end
  local sent = udp:sendto(table.concat(values, '|'), '127.0.0.1', port)
  status = sent and (active and 'Sending driving feedback.' or 'Paused. Feedback is silent.') or 'Local feedback connection unavailable.'
end
function script.windowMain()
  ui.textWrapped(status)
  ui.textWrapped('Brake / ABS: left. Throttle / traction: right.')
  ui.textWrapped('Strength and side tests are in launcher Settings > Controls.')
end
ac.onRelease(function() if udp then udp:close() end end)
'''


def icon():
    """Ícone autoral simples; sem assets do simulador ou da referência."""
    pixels = bytearray()
    for y in range(32):
        pixels.append(0)
        for x in range(32):
            lit = any((x-center)**2+(y-16)**2 < 35 for center in (8, 23))
            pixels.extend((188, 232, 129, 255) if lit else (24, 33, 37, 255))
    def chunk(kind, data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',32,32,8,6,0,0,0))
            +chunk(b'IDAT',zlib.compress(bytes(pixels)))+chunk(b'IEND',b''))


def assets(package):
    path = Path(package)/'launcher/driving-haptics-endpoint.txt'
    wine = ('Z:' if path.as_posix().startswith('/') else '')+path.as_posix()
    quoted = ''.join('\\%03d' % byte for byte in wine.encode('utf-8'))
    return {'manifest.ini': MANIFEST.encode(), APP_ID+'.lua': SCRIPT.encode(),
            'old_man_paths.lua': ('return "'+quoted+'"\n').encode('ascii'), 'icon.png': icon()}


def install(package):
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package/'prepared.json'))
    folder = game/'apps/lua'/APP_ID
    receipt = package/'launcher/driving-haptics-app.json'
    for path in (folder, receipt): safe.check_components(path)
    data = assets(package)
    files = {name: hashlib.sha256(raw).hexdigest() for name,raw in data.items()}
    old_files={}
    if receipt.exists():
        old = safe.read_json(receipt)
        internal = package/'game'
        moved = (isinstance(old, dict) and folder.is_relative_to(internal)
                 and isinstance(old.get('folder'), str)
                 and old['folder'].endswith('/game/'+folder.relative_to(internal).as_posix()))
        if (not isinstance(old,dict) or not isinstance(old.get('files'),dict)
                or not isinstance(old.get('previous_files',{}),dict)
                or (old.get('folder') != str(folder) and not moved) or old.get('revision') != 1
                or set(old.get('files',{})) != set(files)
                or any(type(value) is not str for value in old['files'].values())
                or any(type(value) is not str for value in old.get('previous_files',{}).values())):
            raise ValueError('Driving haptics receipt differs; preserve installed files')
        old_files=old['files']
    elif folder.exists():
        raise ValueError('Unknown driving haptics app; preserve installed files')
    for name, expected in files.items():
        path = folder/name
        safe.check_components(path)
        accepted={expected,old_files.get(name)}
        if receipt.exists():accepted.add(old.get('previous_files',{}).get(name))
        if path.exists() and safe.hash_reference_file(path)[0] not in accepted:
            raise ValueError('Driving haptics app was modified; preserve it')
    previous_files=old.get('previous_files',old_files) if old_files else {}
    record = dict(schema_version=1, revision=1, folder=str(folder), files=files, status='installing',previous_files=previous_files)
    def save():
        receipt.parent.mkdir(parents=True,exist_ok=True)
        temporary = receipt.with_name('driving-haptics-'+uuid.uuid4().hex+'.json')
        safe.write_new_json(temporary, record)
        temporary.replace(receipt)
    save()
    folder.mkdir(parents=True, exist_ok=True)
    for name, raw in data.items():
        path = folder/name
        if not path.exists() or safe.hash_reference_file(path)[0] != files[name]:
            temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
            with temporary.open('xb') as stream: stream.write(raw)
            temporary.replace(path)
    record['status'] = 'ready'
    record.pop('previous_files',None)
    save()
    return record
