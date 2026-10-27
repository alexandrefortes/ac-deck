"""Confirmação pontual de chegada pelo CSP, vinculada à tentativa atual."""
import hashlib
import json
import re
import socket
from pathlib import Path
import uuid

from . import file_io as safe
from . import results

APP_ID = 'old_man_race_finish'
MANIFEST = b'[ABOUT]\nNAME=Old Man Race Finish\nAUTHOR=Old Man Assetto Corsa\nVERSION=1\nDESCRIPTION=Session finish confirmation\n[CORE]\nLAZY=NONE\n'
SCRIPT = r'''
local loaded, context = pcall(require, 'old_man_finish_context')
if not loaded or type(context) ~= 'table' then return end
local generation, saved = 0, false
local boot = string.format('%08x%08x', math.randomKey(), math.randomKey())
local channel, pending = nil, ''
local connected, connection = pcall(function()
  local net = require('shared/socket')
  local peer = assert(net.tcp())
  peer:settimeout(0.05)
  if not peer:connect('127.0.0.1', context.port) then peer:close(); return nil end
  peer:settimeout(0)
  return peer
end)
if connected then channel = connection end
local function flush()
  if not channel then return end
  for _ = 1, 4 do
    if #pending == 0 then return end
    local ok, sent, err, partial = pcall(channel.send, channel, pending)
    if not ok or (not sent and err ~= 'timeout') then
      pcall(channel.close, channel); channel=nil; return
    end
    pending=pending:sub((sent or partial or 0)+1)
    if not sent then return end
  end
end
local function state(action, finished)
  if not channel then return end
  pending=pending..table.concat({'OMF1',context.nonce,boot,action,tostring(generation)},'|')
    ..(finished == nil and '' or '|'..(finished and '1' or '0'))..'\n'
  if #pending > 8192 then
    if channel then pcall(channel.close, channel); channel=nil end
    return
  end
  flush()
end
state('O')
local function integer(n, low, high)
  return type(n) == 'number' and n == n and n % 1 == 0 and n >= low and n <= high
end
local function write(finished, car)
  local data = {schema_version=1, session_id=context.session_id, nonce=context.nonce,
    config_sha256=context.config_sha256, boot_id=boot, generation=generation, finished=finished,
    car=ac.getCarID(0), track=ac.getTrackID(), layout=ac.getTrackLayout() or ''}
  if finished then
    data.position=car.racePosition; data.completed_laps=car.lapCount
    data.skin=ac.getCarSkinID(0); data.target_laps=ac.getSession(ac.getSim().currentSessionIndex).laps
    data.cars={}
    for i=0,ac.getSim().carsCount-1 do data.cars[i+1]=ac.getCarID(i) end
  end
  local ok, result = pcall(io.save, context.path, JSON.stringify(data))
  return ok and result ~= false
end
-- Clear a previous finish before accepting another race in this same process.
write(false)
ac.onSessionStart(function()
  generation=generation+1; saved=false; state('R'); write(false)
end)
ac.onRelease(function()
  if channel then pcall(channel.settimeout, channel, 0.05) end
  state('E', saved)
  if channel then pcall(channel.close, channel); channel=nil end
end)
function script.update(dt)
  flush()
  local car, sim = ac.getCar(0), ac.getSim()
  if saved or not car or sim.isOnlineRace or sim.isReplayActive
    or sim.raceSessionType ~= ac.SessionType.Race or not sim.isSessionStarted
    or not car.physicsAvailable or car.isRaceFinished ~= true then return end
  local session=ac.getSession(sim.currentSessionIndex)
  if not session or session.laps ~= context.target_laps or sim.carsCount ~= context.cars then return end
  if not integer(car.racePosition, 1, context.cars)
    or not integer(car.lapCount, 0, 100000) then return end
  saved=write(true, car)
end
'''


def _quote(value):
    return '"'+''.join('\\%03d' % byte for byte in value.encode('utf-8'))+'"'


class _FinishChannel:
    """Ordered, bounded release state; file I/O cannot hide a restart."""
    def __init__(self, nonce):
        self.nonce, self.receipt = nonce, None
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server.bind(('127.0.0.1', 0))
            self.server.listen(8)
            self.server.setblocking(False)
            self.port = self.server.getsockname()[1]
        except BaseException:
            self.server.close()
            raise

    def sealed(self):
        if self.receipt is not None:
            return self.receipt
        connections = []
        try:
            while len(connections) < 9:
                try:
                    peer, _ = self.server.accept()
                except BlockingIOError:
                    break
                peer.setblocking(False)
                connections.append(peer)
            if not connections or len(connections) > 8:
                raise ValueError('Missing or excessive finish channels')
            latest = None
            for peer in connections:
                raw = bytearray()
                while len(raw) <= 8192:
                    try:
                        chunk = peer.recv(8193-len(raw))
                    except BlockingIOError:
                        raise ValueError('Finish channel was not closed') from None
                    if not chunk:
                        break
                    raw.extend(chunk)
                if len(raw) > 8192 or not raw.endswith(b'\n'):
                    raise ValueError('Incomplete or excessive finish channel')
                boot, generation, ended = None, 0, None
                for index, line in enumerate(raw.decode('ascii').splitlines()):
                    fields = line.split('|')
                    if (len(fields) not in (5, 6) or fields[:2] != ['OMF1', self.nonce]
                            or not re.fullmatch('[0-9a-f]{16}', fields[2])
                            or not re.fullmatch('0|[1-9][0-9]{0,5}', fields[4])
                            or int(fields[4]) > 100000 or ended is not None):
                        raise ValueError('Invalid finish channel frame')
                    action, number = fields[3], int(fields[4])
                    if index == 0 and action == 'O' and len(fields) == 5 and number == 0:
                        boot = fields[2]
                    elif fields[2] != boot:
                        raise ValueError('Finish channel identity differs')
                    elif action == 'R' and len(fields) == 5 and number == generation + 1:
                        generation = number
                    elif action == 'E' and len(fields) == 6 and number == generation and fields[5] in ('0', '1'):
                        ended = fields[5] == '1'
                    else:
                        raise ValueError('Invalid finish channel sequence')
                if ended is None:
                    raise ValueError('Missing finish channel release')
                latest = dict(boot_id=boot, generation=generation, finished=ended)
            if latest['finished'] is not True:
                raise ValueError('Latest race was not finished')
            self.receipt = latest
            return latest
        finally:
            for peer in connections:
                peer.close()

    def close(self):
        self.server.close()


class Capture:
    def __init__(self, game, history, config):
        self.history, self.config = Path(history), config
        self.path = self.history/'finish-capture.json'
        self.nonce = uuid.uuid4().hex
        self.digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        self.channel = _FinishChannel(self.nonce)
        try:
            self._install(game)
        except BaseException:
            self.channel.close()
            raise

    def _install(self, game):
        config = self.config
        folder = safe.source_root(game)/'apps/lua'/APP_ID
        receipt = self.history.parents[1]/'finish-app.json'
        target = ('Z:' if self.path.as_posix().startswith('/') else '')+self.path.as_posix()
        context = ('return {path='+_quote(target)+', session_id='+_quote(self.history.name)
                   +', nonce='+_quote(self.nonce)+', port='+str(self.channel.port)+', config_sha256='+_quote(self.digest)
                   +', cars='+str(len(config['cars']))
                   +', target_laps='+str(config['sessions'][0]['target_laps'])+'}\n').encode('ascii')
        assets = {'manifest.ini': MANIFEST, APP_ID+'.lua': SCRIPT.encode(),
                  'old_man_finish_context.lua': context}
        self.context_path = folder/'old_man_finish_context.lua'
        self.context_hash = hashlib.sha256(context).hexdigest()
        old = {}
        safe.check_components(receipt)
        if receipt.exists():
            old = safe.read_json(receipt)
            recorded_folder = old.get('folder')
            package = self.history.parents[2]
            internal = folder == package/'game/apps/lua'/APP_ID
            old_internal = (isinstance(recorded_folder, str) and Path(recorded_folder).is_absolute()
                            and '..' not in Path(recorded_folder).parts
                            and Path(recorded_folder).parts[-4:] == ('game', 'apps', 'lua', APP_ID))
            if (old.get('schema_version') != 1
                    or recorded_folder != str(folder) and not (internal and old_internal)
                    or set(old.get('files', {})) != set(assets)):
                raise ValueError('Finish app receipt differs; preserve existing files')
        elif folder.exists():
            raise ValueError('Unknown finish app; preserve existing files')
        hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in assets.items()}
        previous = {}
        for name in assets:
            path = folder/name
            safe.check_components(path)
            if path.exists():
                actual = safe.hash_reference_file(path)[0]
                if actual not in (hashes[name], old.get('files', {}).get(name), old.get('previous', {}).get(name)):
                    raise ValueError('Modified finish app; preserve existing files')
                previous[name] = actual
        receipt.parent.mkdir(parents=True, exist_ok=True)
        record = dict(schema_version=1, folder=str(folder), files=hashes, previous=previous)
        results._save(receipt, record, replace=receipt.exists())
        folder.mkdir(parents=True, exist_ok=True)
        for name, raw in assets.items():
            path = folder/name
            results._write(path, raw, replace=path.exists())

    def read(self, started_ns, ended_ns):
        raw, fingerprint = results._read(self.path)
        if len(raw) > 8192 or not started_ns <= fingerprint['mtime_ns'] <= ended_ns:
            raise ValueError('Stale finish capture')
        data = results._json(raw)
        if (not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1
                or data.get('session_id') != self.history.name or data.get('nonce') != self.nonce
                or data.get('config_sha256') != self.digest or data.get('finished') is not True):
            raise ValueError('Finish capture does not match this attempt')
        for key in ('car', 'track', 'layout', 'skin'):
            if not isinstance(data.get(key), str) or data[key].casefold() != self.config[key].casefold():
                raise ValueError('Finish capture content differs')
            data[key] = self.config[key]
        cars=data.get('cars')
        if (not isinstance(cars,list) or len(cars)!=len(self.config['cars'])
                or any(not isinstance(car,str) or car.casefold()!=wanted.casefold()
                       for car,wanted in zip(cars,self.config['cars']))
                or type(data.get('target_laps')) is not int
                or data['target_laps']!=self.config['sessions'][0]['target_laps']):
            raise ValueError('Finish capture race differs')
        data['cars'] = list(self.config['cars'])
        results._integer(data.get('position'), 1, len(self.config['cars']))
        results._integer(data.get('completed_laps'))
        results._integer(data.get('generation'))
        seal = self.channel.sealed()
        if data.get('boot_id') != seal['boot_id'] or data['generation'] != seal['generation']:
            raise ValueError('Finish capture was invalidated by a restart or reload')
        data.pop('nonce')
        return dict(data, sha256=fingerprint['sha256'])

    def close(self):
        self.channel.close()
        safe.check_components(self.context_path)
        if self.context_path.exists() and safe.hash_reference_file(self.context_path)[0] == self.context_hash:
            self.context_path.unlink()
