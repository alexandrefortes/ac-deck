"""Objective cue for the current launcher-owned Rogue attempt."""
import hashlib
from pathlib import Path
import secrets
import socket
import tempfile
import threading
from time import monotonic

from . import file_io as safe
from . import rogue_native_score


APP_ID = 'ac_deck_rogue_goal'
# Exact Lua scripts shipped in Deck builds 114 through 116.
LEGACY_SCRIPT_HASHES = (
    '5def640585d855d5e23642c75b7e389dd005aaf1254018c5398dc4cf03230a20',
    '2f953305c1492c3622ee2c47ef39e6acf366f59de1265956ca179b3a7008473e',
    '89ae30b54a6b25b02153057a8c0c5f83ada34929b73ad8e2223eba5e62186e24',
)
MANIFEST = b'''[ABOUT]
NAME = ac-deck Rogue Goal
AUTHOR = ac-deck
VERSION = 1.0
DESCRIPTION = Shows the current Rogue objective during driving.
REQUIRED_VERSION = 3465

[CORE]
LAZY = NONE
'''

SCRIPT = r'''
local config = ac.INIConfig.raceConfig()
local token = config:get('AC_DECK_ROGUE_HUD', 'TOKEN', '')
local port = config:get('AC_DECK_ROGUE_HUD', 'PORT', 0)
local mode = config:get('SESSION_0', 'TYPE', 0)
local raceCars = mode == 3 and config:get('RACE', 'CARS', 0)
local modes = {[3]='Race', [4]='Hotlap', [5]='Time Attack', [6]='Drift'}
if type(token) ~= 'string' or #token ~= 32 or not token:match('^[0-9a-f]+$')
  or type(port) ~= 'number' or port % 1 ~= 0 or port < 1 or port > 65535
  or not modes[mode] then return end

local udp
local ok = pcall(function()
  udp = assert(require('shared/socket').udp())
  assert(udp:setsockname('127.0.0.1', 0))
  assert(udp:settimeout(0))
end)
if not ok then
  if udp then udp:close() end
  return
end

local loopback = '127.0.0.1'
local sequence, request, target = 0, nil, nil
local requestPhase, lastPhase
local lastSent, expires = -math.huge, -math.huge
local scoreMode = mode == 5 or mode == 6
local generation = math.floor(os.preciseGameTime() * 1000)
local points, pointsExpire = nil, -math.huge
local finalPoints, finalPointsExpire = nil, -math.huge
local function validValue(value, minimum)
  return type(value) == 'number' and value >= minimum and value <= 2147483647
end
local function currentSession(sim)
  return sim and not sim.isReplayOnlyMode and not sim.isOnlineRace
    and sim.currentSessionIndex == 0 and sim.raceSessionType == mode
end
local function send(phase)
  sequence = sequence + 1
  local packet = 'ACDR2|' .. token .. '|' .. string.format('%.0f|%.0f|', sequence, generation) .. phase .. '\n'
  udp:sendto(packet, loopback, port)
  return packet
end

local playerBest, eventComplete, awaitingActive, won, winAnnounced, goalAnnounced
local nativeBestReady = true
ac.onSessionStart(function(sessionIndex, restarted)
  playerBest, eventComplete, awaitingActive, won, winAnnounced = nil, false, true, nil, false
  goalAnnounced = false
  nativeBestReady = false
  generation = generation + 1
  points, finalPoints, request, lastPhase, lastSent = nil, nil, nil, nil, -math.huge
  if sessionIndex == 0 and restarted == true and currentSession(ac.getSim()) then
    send('R')
  end
end)
if mode == 4 then
  ac.onLapCompleted(0, function(carIndex, lapTime, valid)
    local sim = ac.getSim()
    if carIndex == 0 and valid == true and validValue(lapTime, 1) and lapTime % 1 == 0
      and currentSession(sim) and sim.isSessionStarted and not sim.isReplayActive then
      playerBest = math.min(playerBest or lapTime, lapTime)
    end
  end)
end

local function driftResults(sim)
  return mode == 6 and not awaitingActive and sim.isLookingAtSessionResults == true
end

function script.update()
  local sim = ac.getSim()
  if not currentSession(sim) or sim.isReplayActive then return end
  local now = os.preciseClock()
  if mode == 6 and not awaitingActive and sim.isSessionFinished == true then
    eventComplete = true
  end
  local wantsPoints = scoreMode and not awaitingActive and sim.isSessionStarted and not eventComplete
    and not sim.isSessionFinished and not sim.isPaused and not sim.isInMainMenu
    and sim.isWindowForeground and not sim.isLookingAtSessionResults and sim.focusedCar == 0
  local phase = (eventComplete or driftResults(sim)) and won == nil and 'F'
    or wantsPoints and 'A' or 'T'
  if phase ~= 'A' then points = nil end
  if phase ~= 'F' then finalPoints = nil end
  for _ = 1, 4 do
    local response, address, responsePort = udp:receivefrom(256)
    if not response then break end
    if request and address == loopback and responsePort == port and now < lastSent + 2
      and response:sub(1, #request) == request then
      if requestPhase == 'A' then points = nil end
      if requestPhase == 'F' then finalPoints = nil end
      local value = response:sub(#request + 1)
      local goalText, scoreText = value:match('^(%d+)|(%-?%d+)$')
      goalText = goalText or value:match('^%d+$')
      local goal = goalText and #goalText <= 10 and tonumber(goalText)
      if validValue(goal, 1) then
        target, expires, request = goal, lastSent + 2, nil
        local score = scoreText and #scoreText <= 11 and tonumber(scoreText)
        if requestPhase == phase and validValue(score, -2147483648) then
          if phase == 'A' then points, pointsExpire = score, lastSent + 1 end
          if phase == 'F' then finalPoints, finalPointsExpire = score, lastSent + 1 end
        end
      end
    end
  end
  if phase ~= lastPhase or now - lastSent >= 0.5 then
    request, requestPhase, lastPhase, lastSent = send(phase), phase, phase, now
  end
end

local background = rgbm(0.04, 0.06, 0.09, 0.9)
local foreground = rgbm(0.95, 0.97, 1, 1)
local green = rgbm(0.07, 0.36, 0.20, 0.95)
local red = rgbm(0.56, 0.12, 0.15, 0.95)
local function formatTime(ms)
  return string.format('%d:%02d.%03d', math.floor(ms / 60000), math.floor(ms / 1000) % 60, ms % 1000)
end
local function racePosition(car, sim)
  local position = car and car.racePosition
  if validValue(raceCars, 2) and raceCars % 1 == 0 and sim.carsCount == raceCars
    and target <= raceCars and validValue(position, 1) and position % 1 == 0
    and position <= raceCars then return position end
end
local function hotlapBest(car)
  local recorded = car and car.bestLapTimeMs
  local laps = car and car.lapCount
  if laps == 0 then nativeBestReady = true end
  if nativeBestReady and validValue(laps, 1) and laps % 1 == 0 and car.bestLapFromGhost == false
    and validValue(recorded, 1) and recorded % 1 == 0 then
    playerBest = math.min(playerBest or recorded, recorded)
    return playerBest, true
  end
  return playerBest
end
local function progress(car, sim)
  if mode == 3 then
    local position = racePosition(car, sim)
    if position then
      return string.format('P%d / P%d', position, target), position <= target and green or red
    end
    return string.format('Finish P%d or better', target), background
  elseif mode == 4 then
    local best = hotlapBest(car)
    if best then
      return formatTime(best) .. ' / ' .. formatTime(target), best <= target and green or background
    end
    return 'Goal ' .. formatTime(target) .. ' or faster', background
  end
  if points and os.preciseClock() < pointsExpire then
    return string.format('%d / %d pts', points, target), points >= target and green or background
  end
  return string.format('Goal %d pts', target), background
end
local unregister = ui.onExclusiveHUD(function(drawMode)
  if drawMode ~= 'game' and drawMode ~= 'results' then return nil end
  local sim = ac.getSim()
  if not currentSession(sim) or sim.isReplayActive or sim.isInMainMenu
    or not sim.isWindowForeground or (drawMode == 'game' and sim.isPaused) then return nil end

  local car = ac.getCar(0)
  local ended = (mode == 3 and car and car.isRaceFinished == true)
    or (mode ~= 3 and sim.isSessionFinished == true)
  if ended and not awaitingActive then eventComplete = true end
  -- Keep the attempt heartbeat even if regular updates stop on the results screen.
  if drawMode == 'results' or ended or eventComplete then script.update() end
  if not target or os.preciseClock() >= expires then return nil end
  -- The results view can precede CSP's finish flag. Only the native terminal reply can finish Drift here.
  if not eventComplete and driftResults(sim) and finalPoints and os.preciseClock() < finalPointsExpire then
    eventComplete = true
  end

  if eventComplete and won == nil then
    if mode == 3 then
      if ended then
        local position = racePosition(car, sim)
        if position then won = position <= target end
      end
    elseif mode == 4 then
      local best, recorded = hotlapBest(car)
      if best and (recorded or best <= target) then won = best <= target end
    elseif finalPoints and os.preciseClock() < finalPointsExpire then
      won = finalPoints >= target
    end
  end
  if won == true and not winAnnounced then
    winAnnounced = true
    send('W')
  end
  local label, color, liveGoal
  if eventComplete then
    if won == true then label, color = 'Event success', green
    elseif won == false then label, color = 'Event failed', red
    else label, color = 'Result unconfirmed', background end
  else
    if drawMode ~= 'game' or ended or not car or not car.physicsAvailable or not sim.isSessionStarted
      or sim.isLookingAtSessionResults or sim.focusedCar ~= 0 then return nil end
    awaitingActive = false
    local value
    value, color = progress(car, sim)
    label = 'Rogue  |  ' .. modes[mode] .. '  |  ' .. value
    liveGoal = mode ~= 3 and color == green
    if liveGoal and not goalAnnounced then
      goalAnnounced = true
      send('G')
    end
  end

  local size = ui.windowSize()
  local scale = math.max(0.75, math.min(1.5, size.y / 800))
  local fontSize, padding = (eventComplete and 38 or 20) * scale, 9 * scale
  ui.pushDWriteFont('Segoe UI:@System;Weight=SemiBold')
  local textSize = ui.measureDWriteText(label, fontSize)
  local width, height = textSize.x, textSize.y
  local exitLabel = eventComplete and 'Exit to continue'
    or liveGoal and 'You can exit now or keep driving.'
  local exitFont, exitSize = 22 * scale, nil
  local gap = 4 * scale
  if exitLabel then
    exitSize = ui.measureDWriteText(exitLabel, exitFont)
    width = math.max(width, exitSize.x)
    height = height + gap + exitSize.y
  end
  local x = (size.x - width) / 2
  local y = math.max(padding, size.y * (eventComplete and 0.09 or 0.04))
  if textSize.x > 0 and x >= 2 * padding and y + height + padding <= size.y then
    ui.drawRectFilled(vec2(x - 2 * padding, y - padding),
      vec2(x + width + 2 * padding, y + height + padding), color, 5 * scale)
    ui.dwriteDrawText(label, fontSize, vec2((size.x - textSize.x) / 2, y), foreground)
    if exitSize then
      ui.dwriteDrawText(exitLabel, exitFont, vec2((size.x - exitSize.x) / 2, y + textSize.y + gap), foreground)
    end
  end
  ui.popDWriteFont()
  return nil
end, true)

ac.onRelease(function()
  if type(unregister) == 'function' then unregister() end
  udp:close()
end)
'''


def install(game):
    folder = safe.source_root(game)/'apps/lua'/APP_ID
    script_path = folder/(APP_ID+'.lua')
    script_data = SCRIPT.encode('ascii')
    safe.check_components(folder)
    updating = folder.exists()
    if updating:
        stream, _ = safe.open_reference(folder/'manifest.ini')
        with stream:
            if stream.read(len(MANIFEST) + 1) != MANIFEST:
                raise ValueError('Rogue goal app differs; preserve installed files')
        current_hash = hashlib.sha256(script_data).hexdigest()
        digest, _ = safe.hash_reference_file(script_path)
        if digest == current_hash:
            return
        if digest not in LEGACY_SCRIPT_HASHES:
            raise ValueError('Rogue goal app differs; preserve installed files')
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=APP_ID+'-', dir=folder.parent) as temporary:
        staged = Path(temporary) / 'app'
        staged.mkdir()
        staged_script = staged/script_path.name
        with staged_script.open('xb') as stream:
            stream.write(script_data)
        if updating:
            digest, _ = safe.hash_reference_file(script_path)
            if digest in LEGACY_SCRIPT_HASHES:
                staged_script.replace(script_path)
            elif digest != current_hash:
                raise ValueError('Rogue goal app differs; preserve installed files')
            return
        with (staged/'manifest.ini').open('xb') as stream:
            stream.write(MANIFEST)
        safe.rename_new(staged, folder)


class _ScoreWorker:
    def __init__(self, reader, mode, trace):
        self.reader, self.mode, self.trace = reader, mode, trace
        self.changed = threading.Condition()
        self.key = self.request = self.result = self.active_identity = None
        self.generation = 0
        self.closed = False
        threading.Thread(target=self.run, name='rogue-native-score', daemon=True).start()

    def points(self, key, sequence, phase):
        with self.changed:
            if self.closed:
                return None
            if key != self.key:
                self.key = key
                self.result = self.active_identity = None
                self.generation += 1
            self.request = (self.generation, sequence, phase) if phase in (b'A', b'F') else None
            if self.request is None:
                self.result = None
            self.changed.notify()
            if self.result is not None:
                sampled_at, sampled_phase, points = self.result
                if phase == sampled_phase and monotonic() - sampled_at < 1:
                    return points
            return None

    def run(self):
        previous = None
        next_at = 0.0
        reported = set()
        try:
            while True:
                with self.changed:
                    self.changed.wait_for(lambda: self.closed or
                                          (self.request is not None and self.request != previous))
                    if self.closed:
                        return
                    delay = next_at - monotonic()
                    if delay > 0:
                        self.changed.wait(delay)
                        continue
                    previous = self.request
                sampled_at = monotonic()
                status, points = self.reader.sample()
                next_at = sampled_at + 0.5
                terminal = status in ('access_denied', 'ambiguous_process', 'unsupported_executable',
                                      'unsupported_platform', 'unsupported_mode', 'image_changed')
                valid = (status == 'ok' and self.reader.active_mode == self.mode and type(points) is int
                         and -2147483648 <= points <= 2147483647 and self.reader.sample_identity is not None)
                with self.changed:
                    if self.closed:
                        return
                    phase = previous[2]
                    current = (previous[0] == self.generation and self.request is not None
                               and phase == self.request[2])
                    if current:
                        if valid and phase == b'A' and not self.reader.sample_finished:
                            self.active_identity = self.reader.sample_identity
                        else:
                            valid = (valid and phase == b'F' and self.reader.sample_finished
                                     and self.reader.sample_identity == self.active_identity)
                        self.result = (sampled_at, phase, points) if valid else None
                if self.trace is not None and status not in reported and (terminal or (current and valid)):
                    reported.add(status)
                    self.trace('rogue_native_score', status=status, mode=self.mode)
                if terminal:
                    return
        except (OSError, ValueError, RuntimeError):
            return
        finally:
            self.close()
            self.reader.close()

    def close(self):
        with self.changed:
            self.closed = True
            self.result = None
            self.changed.notify()


class Session:
    def __init__(self, session_id, *, on_audio=None):
        self.session_id = session_id
        self.token = secrets.token_hex(16)
        self.prefix = f'ACDR2|{self.token}|'.encode('ascii')
        self.mode = self.target = None
        self.score_mode = self.score_worker = None
        self.on_audio = on_audio
        self.observed = self.terminal_at = self.active_at = None
        self.finished = self.audio_played = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('127.0.0.1', 0))
            self.socket.setblocking(False)
            self.config = dict(TOKEN=self.token, PORT=str(self.socket.getsockname()[1]))
        except BaseException:
            self.close()
            raise

    def set_attempt(self, attempt):
        if attempt['session_id'] != self.session_id or attempt['status'] != 'pending':
            raise ValueError('Invalid Rogue goal attempt')
        mode = self.mode = attempt['selection']['mode']
        target = attempt['target_position'] if mode == 2 else attempt['objective']['target']
        if type(target) is not int or not 1 <= target <= 2147483647:
            raise ValueError('Invalid Rogue goal target')
        self.score_mode = {3: 'time_attack', 4: 'drift'}.get(mode)
        if self.score_mode is not None and attempt['objective'].get('kind') != 'points':
            raise ValueError('Invalid Rogue points objective')
        self.target = str(target).encode('ascii')

    def start_native_score(self, game_exe, process, *, trace=None):
        if self.score_mode is None or self.score_worker is not None:
            return
        reader = rogue_native_score.Reader(game_exe, process, self.score_mode)
        try:
            self.score_worker = _ScoreWorker(reader, self.score_mode, trace)
        except BaseException:
            reader.close()
            raise

    def _audio(self, action):
        if self.on_audio is not None:
            try:
                self.on_audio(action)
            except (OSError, ValueError, RuntimeError):
                pass

    def _request(self, peer, sequence, generation, phase):
        key = peer, generation
        observed = self.observed
        same_generation = observed is not None and key == observed[0]
        if same_generation and sequence <= observed[1]:
            return False, None
        if phase == b'R':
            if (observed is not None and peer == observed[0][0] and generation == observed[0][1] + 1
                    and sequence > observed[1]):
                self.observed = key, sequence
                self.finished = self.audio_played = False
                self.terminal_at = self.active_at = None
                if self.score_worker is not None:
                    self.score_worker.points(key, sequence, b'T')
                self._audio('restart')
            return False, None
        if phase in (b'G', b'W'):
            if phase == b'G':
                fresh = self.active_at is not None and monotonic() - self.active_at < 1
                eligible = not self.finished and (self.mode == 1 or (self.score_mode is not None and fresh))
            else:
                fresh = self.terminal_at is not None and monotonic() - self.terminal_at < 1
                eligible = self.finished and (self.score_mode is None or fresh)
            if same_generation and eligible and not self.audio_played:
                self.observed = key, sequence
                self.audio_played = True
                self._audio('win')
            return False, None
        if not same_generation:
            if observed is not None and generation <= observed[0][1]:
                return False, None
            self.finished, self.terminal_at, self.active_at = False, None, None
        self.observed = key, sequence
        if phase == b'F':
            self.finished = True
        points = self.score_worker.points(key, sequence, phase) if self.score_worker is not None else None
        if phase == b'A' and points is not None and points >= int(self.target):
            self.active_at = monotonic()
        elif phase == b'T':
            self.active_at = None
        if phase == b'F' and points is not None:
            self.terminal_at = monotonic() if points >= int(self.target) else None
        return True, points

    def tick(self):
        for _ in range(8):
            try:
                packet, peer = self.socket.recvfrom(128)
            except BlockingIOError:
                return
            if self.target is None or peer[0] != '127.0.0.1':
                continue
            if not packet.startswith(self.prefix) or not packet.endswith(b'\n'):
                continue
            sequence, separator, metadata = packet[len(self.prefix):-1].partition(b'|')
            if not 1 <= len(sequence) <= 16 or not sequence.isdigit():
                continue
            reply = packet + self.target
            if separator:
                generation, phase_separator, phase = metadata.partition(b'|')
                if not phase_separator:  # Earlier Lua apps sent only the score generation.
                    phase = b'A'
                if (not 1 <= len(generation) <= 16 or not generation.isdigit()
                        or phase not in (b'T', b'A', b'F', b'R', b'W', b'G')):
                    continue
                respond, points = self._request(peer, int(sequence), int(generation), phase)
                if not respond:
                    continue
                if points is not None:
                    reply += b'|' + str(points).encode('ascii')
            self.socket.sendto(reply, peer)

    def close(self):
        if self.score_worker is not None:
            self.score_worker.close()
        self.socket.close()
