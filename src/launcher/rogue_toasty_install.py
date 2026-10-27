"""Instala o app CSP exclusivo do Toasty, atualizando a antiga pasta gerida."""
import hashlib
from pathlib import Path
import re
import struct
import sys
import uuid
import zlib

from . import file_io as safe
from . import installed, rogue_toasty_app


# Legacy installation identity avoids leaving the old observer active on upgrade.
APP_ID = 'old_man_rogue_observer'
MANIFEST = '''[ABOUT]
NAME = Old Man Toasty
AUTHOR = Old Man Assetto Corsa
VERSION = 0.3
DESCRIPTION = Cosmetic Toasty effect. No telemetry counters or challenge penalties.
REQUIRED_VERSION = 3465

[CORE]
LAZY = NONE

[WINDOW_0]
ID = main
NAME = Toasty
ICON = icon.png
FUNCTION_MAIN = windowMain
SIZE = 430, 120
'''

SCRIPT = r'''-- Toasty only: no collision tracking, sporting counters or observation history.
local endpointPath = require('old_man_rogue_paths')
local endpoint = io.load(endpointPath) or ''
local port, token, attempt = endpoint:match('^OMTE1\n(%d+)\n([a-f0-9]+)\n([A-Za-z0-9][A-Za-z0-9_-]*)\n$')
port = tonumber(port)
local enabled = #endpoint <= 4096 and port and port >= 1 and port <= 65535 and token and #token == 32
  and attempt and #attempt <= 96
local sequence, generation = 0, ''
local udp = nil
local toasty, claim = nil, nil
local toastyStatus = 'Toasty is off for this session.'
local lastSent = -math.huge
local state = {sessions=0, restarts=0, eventRestart=0}
local MAX_COUNTER = 9007199254740991

local function integer(value, low, high)
  value = tonumber(value)
  if not value or value ~= value or value % 1 ~= 0 or value < low or value > high then return nil end
  return value
end
local function timestamp(value)
  value = tonumber(value)
  if not value or value ~= value or value < 0 or value > 1e12 then return nil end
  return value
end
local function flag(value, bit) return value == true and bit or 0 end
local function flags(car, sim)
  return flag(car and car.physicsAvailable, 1) + flag(sim.isPaused, 2)
    + flag(sim.isReplayActive, 4) + flag(sim.isInMainMenu or sim.isLookingAtSessionResults or sim.isWindowForeground ~= true, 8)
    + flag(sim.isSessionStarted, 16) + flag(sim.isSessionFinished, 32)
end
local function increment(key)
  if state[key] < MAX_COUNTER then state[key] = state[key] + 1 end
end
local function emit(force)
  if not enabled then return end
  local now = os.preciseClock()
  if not force and now >= lastSent and now - lastSent < 0.25 then return end
  lastSent = now
  if sequence >= MAX_COUNTER then return end
  sequence = sequence + 1
  local car, sim = ac.getCar(0), ac.getSim()
  local values = {'OMTL1', token, generation, tostring(sequence),
    string.format('%.3f', car and timestamp(car.timestamp) or 0), tostring(flags(car, sim)),
    tostring(state.sessions), tostring(state.restarts), tostring(state.eventRestart)}
  if udp then pcall(udp.sendto, udp, table.concat(values, '|'), '127.0.0.1', port) end
end

local function sendClaim()
  if not claim or not udp then return end
  local now = os.preciseClock()
  if now > claim.expires then claim=nil; return end
  if now - claim.lastSent < 0.25 then return end
  emit(true) -- Live context first; a claim must use the same live peer and context
  claim.lastSent = now
  pcall(udp.sendto, udp, claim.packet, '127.0.0.1', port)
end
local function requestClaim(requestAttempt, requestGeneration, episode)
  if requestAttempt ~= attempt or requestGeneration ~= generation or not udp then return end
  local car = ac.getCar(0)
  local stamp = car and timestamp(car.timestamp)
  if not stamp then return end
  local now = os.preciseClock()
  local expires = toasty and toasty.core and toasty.core.pending and toasty.core.pending.expires or now+0.75
  claim = {id=episode, expires=math.min(now+0.75, expires), lastSent=-math.huge,
    packet=table.concat({'OMT1', token, generation, tostring(episode), tostring(state.sessions), string.format('%.3f', stamp)}, '|')}
  sendClaim()
end
local function tickClaims()
  if not udp or not toasty then return end
  for _ = 1, 8 do
    local ok, raw, host, peer = pcall(udp.receivefrom, udp, 256)
    if not ok or not raw then break end
    if #raw <= 256 and host == '127.0.0.1' and tonumber(peer) == port and claim then
      local replyToken, replyGeneration, id, allowed = raw:match('^OMTG1|([a-f0-9]+)|([a-f0-9]+)|(%d+)|([01])$')
      if replyToken == token and replyGeneration == generation and integer(id,1,MAX_COUNTER) == claim.id
        and os.preciseClock() <= claim.expires then
        local episode = claim.id
        claim = nil
        toasty.grant(episode, allowed == '1')
      end
    end
  end
  sendClaim()
end

if enabled then
  generation = string.format('%08x%08x', math.randomKey(), math.randomKey())
  local loaded, socket = pcall(require, 'shared/socket')
  if loaded and type(socket.udp) == 'function' then
    local ok, created = pcall(socket.udp)
    if ok then udp = created end
    if udp then udp:settimeout(0) end
  end
  if udp and type(udp.setsockname) == 'function' and type(udp.receivefrom) == 'function' then
    local bound, result = pcall(udp.setsockname, udp, '127.0.0.1', 0)
    if bound and result then
      local loadedToasty, module = pcall(require, 'old_man_rogue_toasty')
      if loadedToasty then
        local attached, effect = pcall(module.attach, {attempt_id=attempt, generation=generation,
          clock=os.preciseClock, request_claim=requestClaim, cancel_claim=function() claim=nil end})
        if attached then toasty=effect else toastyStatus='Toasty setup unavailable.' end
      else toastyStatus='Toasty module unavailable.' end
    else toastyStatus='Toasty authorization connection unavailable.' end
  else toastyStatus='Toasty authorization connection unavailable.' end
  ac.onSessionStart(function(sessionIndex, restarted)
    state.eventRestart = restarted == true and 1 or 0
    increment('sessions')
    if restarted == true then increment('restarts') end
    if toasty then
      if restarted == true then toasty.restart() else toasty.invalidate() end
    end
    claim = nil
    emit(true)
  end)
  ac.onCarJumped(0, function(carIndex)
    if carIndex == 0 then
      if toasty then toasty.invalidate() end
      claim = nil
    end
  end)
end

function script.update(dt)
  if not enabled then return end
  emit(false)
  if toasty then
    local ok = pcall(toasty.update, dt)
    if not ok then pcall(toasty.invalidate); claim=nil; toastyStatus='Toasty update unavailable.' end
    tickClaims()
  end
end

function script.windowMain()
  ui.textWrapped(toasty and toasty.status() or toastyStatus)
end

ac.onRelease(function()
  if toasty then pcall(toasty.dispose) end
  claim = nil
  if udp then pcall(udp.close, udp) end
end)
'''


def icon():
    """Pequeno olho geométrico autoral; sem imagem de terceiros."""
    pixels = bytearray()
    for y in range(32):
        pixels.append(0)
        for x in range(32):
            eye = abs(x - 15.5) + 1.7 * abs(y - 15.5) < 13
            pupil = (x - 15.5)**2 + (y - 15.5)**2 < 15
            pixels.extend((190, 232, 140, 255) if eye and not pupil else (24, 33, 37, 255))
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(pixels))) + chunk(b'IEND', b''))


def assets(package, *, asset_root=None, session_id=None):
    if session_id is not None:
        if not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', session_id):
            raise ValueError('Invalid Toasty session identity')
        path = Path(package) / 'launcher/sessions' / session_id / 'rogue-toasty-endpoint.txt'
    else:
        path = Path(package) / 'launcher/rogue-toasty-endpoint.txt'
    wine = ('Z:' if path.as_posix().startswith('/') else '') + path.as_posix()
    quoted = ''.join('\\%03d' % byte for byte in wine.encode('utf-8'))
    if asset_root is None:
        root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
        asset_root = root / 'assets/rogue-toasty'
    from . import rogue_toasty_assets
    try:
        media = rogue_toasty_assets.load_assets(asset_root)
    except (OSError, ValueError, RuntimeError):
        media = {}  # Missing assets disable only the cosmetic effect.
    data = {'manifest.ini': MANIFEST.encode(), APP_ID + '.lua': SCRIPT.encode(),
            'old_man_rogue_paths.lua': ('return "' + quoted + '"\n').encode('ascii'), 'icon.png': icon()}
    data.update(rogue_toasty_app.assets(enabled=set(media) == {'toasty.png', 'toasty.wav'}))
    data.update(media)
    return data


def install(package, *, asset_root=None, session_id=None):
    """Instala/repara somente arquivos próprios conhecidos, preservando edições."""
    package = safe.source_root(package)
    game = installed.game_path(package, safe.read_json(package / 'prepared.json'))
    folder = game / 'apps/lua' / APP_ID
    receipt = package / 'launcher/rogue-observer-app.json'
    for path in (folder, receipt):
        safe.check_components(path)
    data = assets(package, asset_root=asset_root, session_id=session_id)
    files = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}
    legacy = {'manifest.ini', APP_ID + '.lua', 'old_man_rogue_paths.lua', 'icon.png'}
    known = legacy | set(rogue_toasty_app.assets(enabled=False)) | {'toasty.png', 'toasty.wav'}
    old_files, old = {}, {}
    if receipt.exists():
        old = safe.read_json(receipt)
        if (not isinstance(old, dict) or not isinstance(old.get('files'), dict)
                or not isinstance(old.get('previous_files', {}), dict)
                or old.get('schema_version') != 1 or old.get('revision') not in (1, 2)
                or old.get('status') not in ('installing', 'ready')
                or not isinstance(old.get('folder'), str)
                or not old['folder'].replace('\\', '/').endswith('/apps/lua/' + APP_ID)
                or not legacy <= set(old['files']) <= known
                or not set(old.get('previous_files', {})) <= known
                or any(not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value)
                       for value in (*old['files'].values(), *old.get('previous_files', {}).values()))):
            raise ValueError('Toasty receipt differs; preserve installed files')
        old_files = old['files']
    elif folder.exists():
        raise ValueError('Unknown Toasty app; preserve installed files')
    actual_files = {}
    for name in set(files) | set(old_files) | set(old.get('previous_files', {})):
        expected = files.get(name)
        path = folder / name
        safe.check_components(path)
        accepted = {expected, old_files.get(name), old.get('previous_files', {}).get(name)}
        if path.exists():
            if old and name not in old_files and name not in old.get('previous_files', {}):
                raise ValueError('Unknown Toasty file; preserve it')
            actual = safe.hash_reference_file(path)[0]
            if actual not in accepted:
                raise ValueError('Toasty app was modified; preserve it')
            actual_files[name] = actual
    # Keep ownership of older media if a new distribution is unavailable; never delete it.
    managed = {**old_files, **files}
    record = dict(schema_version=1, revision=2, folder=str(folder), files=managed,
                  status='installing', previous_files=actual_files,
                  toasty_ready='toasty.png' in data and 'toasty.wav' in data)
    def save():
        receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt.with_name('rogue-observer-' + uuid.uuid4().hex + '.json')
        safe.write_new_json(temporary, record)
        temporary.replace(receipt)
    save()
    folder.mkdir(parents=True, exist_ok=True)
    for name, raw in data.items():
        path = folder / name
        if not path.exists() or safe.hash_reference_file(path)[0] != files[name]:
            temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.new')
            with temporary.open('xb') as stream:
                stream.write(raw)
            temporary.replace(path)
    record['status'] = 'ready'
    record.pop('previous_files', None)
    save()
    return record
