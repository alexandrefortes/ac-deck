"""Efeito Toasty cosmético no HUD CSP, com reserva por corrida pelo host."""

PROBABILITY = 0.15
CORE = r'''-- Pure state machine: no CSP, I/O, audio, rendering or network at load.
local M = {}
function M.new(options, effects, claims)
  local s = {attempt=assert(options.attempt_id), generation=assert(options.generation),
    probability=options.probability or 0.15, duration=0.85, request_timeout=0.75,
    cooldown=60, not_before=0, episode=0, spent=false, active=false,
    status='Waiting for a four-wheel excursion.'}
  local function cancel_pending()
    s.pending = nil
    if claims.cancel then claims.cancel() end
  end
  function s:invalidate()
    self.active, self.armed, self.excursion = false, false, false
    self.last_clock, self.started_at = nil, nil
    cancel_pending(); effects.stop()
    self.status = self.spent and 'Toasty already reserved for this race.' or 'Toasty paused; waiting for a new excursion.'
  end
  function s:restart()
    self:invalidate()
    self.spent, self.not_before = false, 0
    -- Keep episode monotonic: an old grant cannot match the new race's request.
    self.status = 'Race restarted; waiting for a new four-wheel excursion.'
  end
  function s:update(f)
    local active = f.physics and f.started and not f.finished and not f.paused
      and not f.replay and not f.menu and not f.results and f.foreground
    local wheels = f.wheels
    if not active or type(wheels) ~= 'number' or wheels ~= wheels or
      wheels % 1 ~= 0 or wheels < 0 or wheels > 4 then self:invalidate(); return end
    local now = effects.now()
    if self.last_clock and now < self.last_clock then self:invalidate() end
    self.last_clock, self.active = now, true
    if self.started_at and now - self.started_at >= self.duration then
      effects.stop(); self.started_at = nil
    end
    if self.pending and now > self.pending.expires then
      cancel_pending()
      self.status = 'Toasty suppressed: host or assets unavailable.'
    end
    if self.spent then return end
    if not self.armed then
      if wheels == 0 then self.armed = true end
      return -- loading outside or midway across the boundary is not an excursion
    end
    if wheels == 0 then self.excursion = false end
    if wheels == 4 and not self.excursion then
      self.episode, self.excursion = self.episode + 1, true
      if self.pending then return end -- keep the first event's immutable claim
      if effects.now() < self.not_before or (options.random or math.random)() >= self.probability then
        self.status = 'Toasty not selected for this excursion.'; return
      end
      if not effects.ready() then self.status='Toasty assets not ready at track exit.'; return end
      self.pending = {episode=self.episode, expires=now+self.request_timeout, requested=true}
      self.status = 'Waiting for authorization from the active Rogue session.'
      claims.request(self.attempt, self.generation, self.episode)
    end
  end
  function s:grant(attempt, generation, episode, allowed)
    local p = self.pending
    if not p or not p.requested or not self.active or effects.now() > p.expires or
      attempt ~= self.attempt or generation ~= self.generation or episode ~= p.episode then return false end
    if allowed then
      p.granted, self.spent = true, true -- host already persisted the reservation
    else
      cancel_pending()
      self.status = 'Toasty not authorized for this race.'
    end
    return true
  end
  function s:render(mode)
    if mode ~= 'game' then self:invalidate(); return nil end
    if not self.active then return nil end
    local now, p = effects.now(), self.pending
    if not self.started_at and p and p.granted and now <= p.expires and effects.ready() then
      self.pending = nil
      local ok, started = pcall(effects.start)
      if not ok or not started then effects.stop(); self.status='Toasty audio unavailable.'; return nil end
      self.started_at, self.not_before = now, now + self.cooldown
      self.status = 'Toasty playing.'
    end
    if self.started_at then
      local age = now - self.started_at
      if age >= self.duration then
        effects.stop(); self.started_at=nil; self.status='Toasty already reserved for this race.'
      else
        local ok, drawn = pcall(effects.draw, age, self.duration)
        if not ok or not drawn then effects.stop(); self.started_at=nil; self.status='Toasty image unavailable.' end
      end
    end
    return nil -- preserve AC HUD and inputs
  end
  return s
end
return M
'''

ADAPTER = r'''-- Cosmetic CSP adapter; this module performs no work until attach().
local M = {}
function M.attach(context)
  local config = require('old_man_rogue_toasty_config')
  if not config.enabled then
    return {update=function() end, invalidate=function() end, restart=function() end, grant=function() return false end,
      dispose=function() end, status=function() return 'Toasty assets unavailable.' end}
  end
  local Core = require('old_man_rogue_toasty_core')
  local root = ac.getFolder(ac.FolderID.ScriptOrigin)
  local imagePath, audioPath = root .. '/toasty.png', root .. '/toasty.wav'
  local audio, imageReady, disposed, unregister = nil, false, false, nil
  local effects = {now=context.clock}
  function effects.stop()
    if audio then pcall(function() audio:dispose() end); audio=nil end
  end
  function effects.prepare()
    imageReady = ui.isImageReady(imagePath) == true
    if imageReady and not audio and ac.isAudioReady() then
      audio = ac.AudioEvent.fromFile({filename=audioPath, use3D=false, useOcclusion=false, loop=false}, false)
      audio.volume = 1.0
      audio.cameraInteriorMultiplier, audio.cameraExteriorMultiplier, audio.cameraTrackMultiplier = 1, 1, 1
    end
  end
  function effects.ready()
    return imageReady and audio and audio:isValid() and ac.isAudioReady()
  end
  function effects.start()
    if not effects.ready() then return false end
    audio:start(); return true
  end
  function effects.draw(age, duration)
    if not imageReady then return false end
    local size = ui.windowSize()
    if not size or size.x <= 0 or size.y <= 0 then return false end
    local side = math.min(200, math.floor(size.x * 0.125))
    local shift = side * (1 - math.min(1, (duration-age)/0.12))
    ui.drawImage(imagePath, vec2(size.x-side-16, size.y-side+shift),
      vec2(size.x-16, size.y+shift), rgbm.colors.white)
    return true
  end
  local core = Core.new({attempt_id=context.attempt_id, generation=context.generation,
    probability=config.probability, random=context.random}, effects,
    {request=context.request_claim, cancel=context.cancel_claim})
  local app = {core=core}
  local function frame()
    local car, sim = ac.getCar(0), ac.getSim()
    return {physics=car and car.physicsAvailable == true, started=sim.isSessionStarted == true,
      finished=sim.isSessionFinished, paused=sim.isPaused, replay=sim.isReplayActive,
      menu=sim.isInMainMenu, results=sim.isLookingAtSessionResults,
      foreground=sim.isWindowForeground == true, wheels=car and car.wheelsOutside}
  end
  local function active(f)
    return f.physics and f.started and not f.finished and not f.paused and not f.replay
      and not f.menu and not f.results and f.foreground
  end
  function app.update()
    if disposed then return end
    local f = frame()
    if active(f) and (not core.spent or core.pending or core.started_at) then
      local ok = pcall(effects.prepare)
      if not ok then core:invalidate(); core.status='Toasty assets or audio unavailable.'; return end
    end
    core:update(f)
  end
  function app.grant(episode, allowed)
    return core:grant(context.attempt_id, context.generation, episode, allowed)
  end
  function app.invalidate() core:invalidate() end
  function app.restart() core:restart() end
  function app.status() return core.status end
  function app.dispose()
    if disposed then return end
    disposed=true; core:invalidate()
    if type(unregister)=='function' then unregister() end
  end
  unregister = ui.onExclusiveHUD(function(mode)
    if disposed then return nil end
    local f = frame() -- recheck guards even if pause/focus changed after update
    if mode ~= 'game' or not active(f) or type(f.wheels) ~= 'number' or f.wheels < 0 or f.wheels > 4 then
      core:invalidate(); return nil
    end
    return core:render(mode)
  end, true)
  return app
end
return M
'''


def assets(*, enabled):
    return {'old_man_rogue_toasty_core.lua': CORE.encode(),
            'old_man_rogue_toasty.lua': ADAPTER.encode(),
            'old_man_rogue_toasty_config.lua':
                ('return {enabled=' + ('true' if enabled else 'false')
                 + ', probability=' + str(PROBABILITY) + '}\n').encode('ascii')}
