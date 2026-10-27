"""Telemetria CSP local -> dois canais de vibração, sem controlar entradas.

Referência de eventos/envelopes: ACC DualSense Feedback 1.0.1 (Adudumax,
MIT; ver licenses/ACC-DualSense-Feedback.txt). Limiares e ganhos do Deck
são iniciais, não calibração observada no aparelho.
"""
import math
import secrets
import socket
import time
from pathlib import Path

DEFAULTS = dict(driving_haptics=True, haptics_left_pct=50, haptics_right_pct=50)
SETTINGS = {'driving_haptics': 'Driving haptics (CSP)',
            'haptics_left_pct': 'Left haptics strength',
            'haptics_right_pct': 'Right haptics strength'}
STALE_SECONDS = 0.15
SCALARS = ('stamp', 'speed', 'gas', 'brake', 'gear', 'rpm', 'rpm_max',
           'steer', 'abs', 'tc', 'drive')
VECTORS = {'ratio': 4, 'angle': 4, 'omega': 4, 'radius': 4,
           'suspension': 4, 'surface': 4, 'damage': 5}
FIELD_COUNT = 4 + len(SCALARS) + sum(VECTORS.values())


def validate(selection):
    if 'driving_haptics' in selection and type(selection['driving_haptics']) is not bool:
        raise ValueError('Driving haptics must be On or Off')
    for key in ('haptics_left_pct', 'haptics_right_pct'):
        value = selection.get(key, DEFAULTS[key])
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError('Haptics strength must be an integer from 0 to 100')


def decode(raw, token):
    """Contrato numérico limitado. Não aceita JSON, nomes ou dados do jogador."""
    if len(raw) > 2048:
        raise ValueError('Haptics packet too large')
    parts = raw.decode('ascii').split('|')
    if len(parts) != FIELD_COUNT or parts[0] != 'OMH1' or parts[1] != token:
        raise ValueError('Haptics packet identity differs')
    seq, active = int(parts[2]), int(parts[3])
    if not 0 < seq < 2**53 or parts[3] not in ('0', '1'):
        raise ValueError('Invalid haptics sequence or state')
    values = [float(value) for value in parts[4:]]
    if any(not math.isfinite(value) or abs(value) > 1e12 for value in values):
        raise ValueError('Invalid haptics telemetry')
    frame = dict(zip(SCALARS, values))
    at = len(SCALARS)
    for key, size in VECTORS.items():
        frame[key] = values[at:at+size]
        at += size
    if (not 0 <= frame['gas'] <= 1 or not 0 <= frame['brake'] <= 1
            or frame['abs'] not in (0, 1) or frame['tc'] not in (0, 1)
            or frame['drive'] not in (-1, 0, 1, 2, 3)
            or frame['gear'] != int(frame['gear']) or not -1 <= frame['gear'] <= 20):
        raise ValueError('Invalid haptics controls')
    frame.update(seq=seq, active=bool(active))
    return frame


def clamp(value):
    return max(0.0, min(1.0, value))


def ramp(value, start, end):
    x = clamp((value-start)/(end-start))
    return x*x*(3-2*x)


def pulse(now, hz):
    return 1.0 if (now*hz) % 1 < 0.45 else 0.12


class Engine:
    def __init__(self):
        self.envelopes = {}
        self.previous = None
        self.last_time = None
        self.shift_until = self.impact_until = 0.0
        self.impact = (0.0, 0.0)

    def compute(self, frame, now):
        if not frame['active']:
            self.__init__()
            return (0.0, 0.0)
        dt = 0.01 if self.last_time is None else max(0.001, min(0.05, now-self.last_time))
        self.last_time = now
        speed = abs(frame['speed'])/3.6
        moving = ramp(speed, 1, 6)
        brake, gas = frame['brake'], frame['gas']
        lock = 0.0
        for index in range(4):
            radius = frame['radius'][index]
            tyre_speed = abs(frame['omega'][index])*radius
            if 0.05 < radius < 2 and speed > 2 and tyre_speed < speed*0.78:
                lock = max(lock, ramp(abs(frame['ratio'][index]), 0.10, 0.5))
        lock *= ramp(brake, 0.08, 0.5)*moving
        driven = (0, 1) if frame['drive'] == 1 else (2, 3) if frame['drive'] == 0 else range(4)
        spin = 0.0
        for index in driven:
            radius = frame['radius'][index]
            tyre_speed = abs(frame['omega'][index])*radius
            if 0.05 < radius < 2 and tyre_speed-speed > max(1.5, speed*0.12):
                spin = max(spin, ramp(abs(frame['ratio'][index]), 0.1, 0.65))
        spin *= ramp(gas, 0.1, 0.65)

        targets = {'abs': frame['abs']*brake*moving, 'lock': lock*(1-frame['abs']),
                   'tc': frame['tc']*gas, 'spin': spin*(1-frame['tc'])}
        for key, target in targets.items():
            old = self.envelopes.get(key, 0.0)
            tau = 0.025 if target > old else 0.10
            self.envelopes[key] = old+(target-old)*(1-math.exp(-dt/tau))
        e = self.envelopes
        left = max(0.12*brake*moving, 0.78*e['abs']*pulse(now, 13), 0.88*e['lock']*pulse(now, 8))
        right = max(0.07*gas*moving, 0.68*e['tc']*pulse(now, 11), 0.80*e['spin']*pulse(now, 7))
        # CSP exposes wheel slip angles in degrees, unlike the ACC source.
        front = ramp(max(abs(v) for v in frame['angle'][:2]), 6, 20)*moving
        rear = ramp(max(abs(v) for v in frame['angle'][2:]), 6, 20)*moving
        left = max(left, 0.28*front*pulse(now, 18))
        right = max(right, 0.30*rear*pulse(now, 22))
        steering = ramp(abs(frame['steer']), 0.90, 0.99)*moving
        # Direction cues are warnings; they never change steering input/FFB.
        left = max(left, 0.18*steering*pulse(now, 5))
        right = max(right, 0.18*steering*pulse(now, 5))
        if self.previous is not None:
            old = self.previous
            if frame['gear'] > old['gear'] > 0 and gas > 0.15 and speed > 2:
                self.shift_until = now+0.075
            if frame['stamp'] != old['stamp']:
                for indices, side in (((0, 2), 0), ((1, 3), 1)):
                    shock = max(abs(frame['suspension'][i]-old['suspension'][i]) for i in indices)
                    surface = max(abs(frame['surface'][i]) for i in indices)
                    detail = moving*min(0.28, shock*3+surface*0.07)*pulse(now, 30)
                    if side == 0: left = max(left, detail)
                    else: right = max(right, detail)
                damage = [max(0, a-b) for a,b in zip(frame['damage'], old['damage'])]
                if max(damage) > 0.1:
                    self.impact_until = now+0.12
                    strength = min(0.65, max(damage)/20)
                    self.impact = (strength if max(damage[0],damage[1],damage[4],damage[2]) > 0.1 else 0,
                                   strength if max(damage[0],damage[1],damage[4],damage[3]) > 0.1 else 0)
        if now < self.shift_until:
            right = max(right, 0.42)
        if frame['rpm_max'] > 1000 and gas > 0.6:
            right = max(right, 0.30*ramp(frame['rpm']/frame['rpm_max'], 0.95, 0.995)*pulse(now, 16))
        if now < self.impact_until:
            left, right = max(left, self.impact[0]), max(right, self.impact[1])
        self.previous = frame
        return clamp(left), clamp(right)


class Session:
    """Receptor por corrida, só em loopback; sem escuta entre sessões."""
    def __init__(self, endpoint, selection, *, clock=time.monotonic):
        validate(selection)
        self.clock = clock
        self.endpoint = Path(endpoint)
        self.token = secrets.token_hex(16)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('127.0.0.1', 0))
            self.socket.setblocking(False)
            temporary=self.endpoint.with_name(self.endpoint.name+'.'+self.token+'.new')
            with temporary.open('x',encoding='ascii',newline='\n') as stream:
                stream.write(str(self.socket.getsockname()[1])+'\n'+self.token+'\n')
            temporary.replace(self.endpoint)
        except BaseException:
            self.socket.close()
            raise
        self.gains = tuple(selection.get(key, DEFAULTS[key])/100 for key in ('haptics_left_pct','haptics_right_pct'))
        self.engine = Engine()
        self.latest = None
        self.last_seq = 0
        self.fresh_at = None
        self.count = 0
        self.status = 'waiting_for_telemetry'

    def tick(self, window):
        now = self.clock()
        for _ in range(64):
            try:
                raw, peer = self.socket.recvfrom(2049)
            except BlockingIOError:
                break
            if peer[0] != '127.0.0.1':
                continue
            try:
                frame = decode(raw, self.token)
            except (ValueError, UnicodeError, OverflowError):
                continue
            if frame['seq'] <= self.last_seq:
                continue
            self.last_seq = frame['seq']
            if self.latest is None or frame['stamp'] != self.latest['stamp'] or not frame['active']:
                self.fresh_at = now
            self.latest = frame
            self.count += 1
        active = self.latest is not None and self.fresh_at is not None and now-self.fresh_at <= STALE_SECONDS
        if active and self.latest['active']:
            values = self.engine.compute(self.latest, now)
            values = tuple(value*gain for value,gain in zip(values,self.gains))
            ok = window.driving_rumble(*values)
            self.status = 'active' if ok else 'output_unavailable'
        else:
            self.engine = Engine()
            window.driving_rumble(0, 0)
            self.status = 'paused' if active else 'waiting_for_telemetry' if self.latest is None else 'stale_telemetry'

    def close(self):
        self.socket.close()
        # Only remove our own endpoint, never a replacement created by a peer.
        try:
            if (not self.endpoint.is_symlink() and self.endpoint.stat().st_nlink == 1
                    and self.endpoint.read_bytes().endswith(b'\n'+self.token.encode('ascii')+b'\n')):
                self.endpoint.unlink()
        except FileNotFoundError:
            pass
