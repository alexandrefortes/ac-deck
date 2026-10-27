"""Ditado pontual: SDL2, áudio em memória e uma transcrição após Stop.

Nenhum dispositivo ou rede é aberto ao importar. Chamador habilita a função,
inicia Capture e solicita transcribe explicitamente; não há retry automático.
"""
import ctypes as C
import json
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

from . import ai_preferences, api_credentials
from .ai_events import NoRedirect

MODEL = 'gpt-transcribe'
ENDPOINT = 'https://api.openai.com/v1/audio/transcriptions'
SAMPLE_RATE, MAX_SECONDS, TIMEOUT = 16000, 60, 45
MAX_PCM = SAMPLE_RATE*2*MAX_SECONDS
MAX_RESPONSE = 64*1024


class DictationError(ValueError):
    def __init__(self, message, *, http_status=None, parameter=None):
        super().__init__(message)
        self.http_status = http_status
        self.parameter = parameter


FAILURE = 'Transcription failed. Draft kept; no retry was sent.'
NETWORK_FAILURE = 'Transcription connection failed or timed out. Draft kept; no retry was sent.'
TLS_FAILURE = 'Transcription TLS/certificate check failed. Draft kept; no retry was sent.'
NO_AUDIO = 'No audio received from microphone. Nothing was sent; draft kept.'
SILENT_AUDIO = 'Microphone signal is silent. Check input/mute; nothing was sent. Draft kept.'
MISSING_INPUT = 'Selected microphone is unavailable. Choose an input; nothing was sent.'
BAD_RESPONSE = 'Unexpected transcription response format. Draft kept; no retry was sent.'
API_ERRORS = {
    'invalid_api_key': 'Transcription API key was rejected. Draft kept; check the saved key.',
    'insufficient_quota': 'Transcription quota is unavailable. Draft kept; check API billing.',
    'model_not_found': 'Transcription model is unavailable for this API key. Draft kept.',
    'audio_too_short': 'Recording is too short for transcription. Draft kept.',
    'invalid_audio': 'Transcription could not read the audio. Draft kept.',
    'unsupported_format': 'Transcription rejected the audio format. Draft kept.'}
SAFE_ERRORS = frozenset(API_ERRORS.values()) | frozenset((
    FAILURE, NETWORK_FAILURE, TLS_FAILURE, NO_AUDIO, SILENT_AUDIO, MISSING_INPUT, BAD_RESPONSE,
    'No usable audio. Record again or type your custom prompt.',
    'No speech was transcribed. The draft was preserved.',
    'Transcript exceeds 8 KiB. Draft kept; no text was cut.',
    'Transcription response is too large. Type or record a shorter prompt.',
    'Enable remote dictation and API key reuse before recording.'))
PARAMETERS = {'file': 'audio file', 'model': 'model', 'languages': 'language hint',
              'languages[]': 'language hint', 'response_format': 'response format'}


def public_message(error):
    """Exibe apenas motivos locais fixos ou status/campo HTTP reconhecidos."""
    if isinstance(error, DictationError):
        value = str(error)
        if value in API_ERRORS.values():
            return value
        status = error.http_status
        if type(status) is int and 100 <= status <= 599:
            if status == 401:
                return API_ERRORS['invalid_api_key']
            if status == 403:
                return 'Transcription access denied (HTTP 403). Draft kept; check model access.'
            if status == 429:
                return 'Transcription rate/quota limit (HTTP 429). Draft kept; no retry was sent.'
            parameter = PARAMETERS.get(error.parameter) if isinstance(error.parameter, str) else None
            detail = ', '+parameter if parameter else ''
            return f'Transcription rejected (HTTP {status}{detail}). Draft kept; no retry was sent.'
        if value in SAFE_ERRORS:
            return value
    return FAILURE


def wipe(buffer):
    if isinstance(buffer, bytearray):
        buffer[:] = b'\0'*len(buffer)
        buffer.clear()


def signal_peak(pcm):
    """Pico PCM16 little endian; não classifica fala nem conserva amostras."""
    return max((abs(sample[0]) for sample in struct.iter_unpack('<h', pcm)), default=0)


def _input_names(sdl):
    count = sdl.SDL_GetNumAudioDevices(1)
    names = []
    for index in range(max(0, count)):
        raw = sdl.SDL_GetAudioDeviceName(index, 1)
        if not raw:
            continue
        try:
            name = raw.decode('utf-8')
            ai_preferences.clean(dict(voice_device=name))
        except (ValueError, UnicodeError):
            continue
        if name and name not in names:
            names.append(name)
    return names


def microphones(sdl):
    """Enumera entradas após ação do usuário; não abre dispositivo nem rede."""
    probe = Capture(sdl)
    try:
        probe._bind()
        if probe._init_audio() != 0:
            raise DictationError(MISSING_INPUT)
        probe.initialized = True
        return _input_names(sdl)
    finally:
        probe._release()


class AudioSpec(C.Structure):
    _fields_ = [('freq', C.c_int), ('format', C.c_uint16), ('channels', C.c_uint8),
                ('silence', C.c_uint8), ('samples', C.c_uint16), ('padding', C.c_uint16),
                ('size', C.c_uint32), ('callback', C.c_void_p), ('userdata', C.c_void_p)]


class Capture:
    """Um dispositivo padrão; fila drenada fora do desenho da interface."""
    def __init__(self, sdl, *, device='', clock=time.monotonic):
        self.sdl, self.clock = sdl, clock
        self.input_name = ai_preferences.clean(dict(voice_device=device))['voice_device']
        self.pcm = bytearray()
        self.stop_event = threading.Event()
        self.thread = None
        self.error = ''
        self.started = None
        self.device = 0
        self.initialized = False
        self.limited = False
        self.level = 0

    def _bind(self):
        signatures = {
            'SDL_InitSubSystem': (C.c_int, [C.c_uint32]),
            'SDL_QuitSubSystem': (None, [C.c_uint32]),
            'SDL_WasInit': (C.c_uint32, [C.c_uint32]),
            'SDL_GetHint': (C.c_char_p, [C.c_char_p]),
            'SDL_SetHintWithPriority': (C.c_int, [C.c_char_p, C.c_char_p, C.c_int]),
            'SDL_ResetHint': (C.c_int, [C.c_char_p]),
            'SDL_GetNumAudioDevices': (C.c_int, [C.c_int]),
            'SDL_GetAudioDeviceName': (C.c_char_p, [C.c_int, C.c_int]),
            'SDL_OpenAudioDevice': (C.c_uint32, [C.c_char_p, C.c_int, C.POINTER(AudioSpec), C.POINTER(AudioSpec), C.c_int]),
            'SDL_PauseAudioDevice': (None, [C.c_uint32, C.c_int]),
            'SDL_GetQueuedAudioSize': (C.c_uint32, [C.c_uint32]),
            'SDL_DequeueAudio': (C.c_uint32, [C.c_uint32, C.c_void_p, C.c_uint32]),
            'SDL_ClearQueuedAudio': (None, [C.c_uint32]),
            'SDL_CloseAudioDevice': (None, [C.c_uint32]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.sdl, name)
            function.restype, function.argtypes = result, args

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    @property
    def seconds(self):
        return min(MAX_SECONDS, max(0, self.clock()-self.started)) if self.started is not None else 0

    @property
    def captured_seconds(self):
        return len(self.pcm)/(SAMPLE_RATE*2)

    def _init_audio(self):
        # SDL 2.30 PulseAudio can stall before delivering any captured bytes
        # (libsdl-org/SDL#9706). Prefer PipeWire directly for this capture only.
        # Keep explicit driver choices and already initialized audio untouched.
        hint = b'SDL_AUDIODRIVER'
        changed = False
        try:
            if (sys.platform.startswith('linux') and not self.sdl.SDL_WasInit(0x10)
                    and not self.sdl.SDL_GetHint(hint)):
                changed = bool(self.sdl.SDL_SetHintWithPriority(hint, b'pipewire,pulseaudio,alsa', 0))
            return self.sdl.SDL_InitSubSystem(0x10)
        finally:
            if changed:
                self.sdl.SDL_ResetHint(hint)

    def start(self):
        if self.thread is not None:
            raise DictationError('Dictation has already started.')
        try:
            self._bind()
            if self._init_audio() != 0:
                raise DictationError('Microphone unavailable. You can still type your custom prompt.')
            self.initialized = True
            if self.input_name and self.input_name not in _input_names(self.sdl):
                raise DictationError(MISSING_INPUT)
            wanted = AudioSpec(freq=SAMPLE_RATE, format=0x8010, channels=1, samples=1024)
            actual = AudioSpec()
            name = self.input_name.encode('utf-8') if self.input_name else None
            self.device = self.sdl.SDL_OpenAudioDevice(name, 1, C.byref(wanted), C.byref(actual), 0)
            if not self.device or (actual.freq, actual.format, actual.channels) != (SAMPLE_RATE, 0x8010, 1):
                raise DictationError('Compatible microphone unavailable. You can still type your custom prompt.')
            self.started = self.clock()
            self.sdl.SDL_PauseAudioDevice(self.device, 0)
            self.thread = threading.Thread(target=self._read, name='preference-dictation', daemon=True)
            self.thread.start()
            return self
        except Exception as error:
            self._release()
            if isinstance(error, DictationError) and str(error) == MISSING_INPUT:
                raise
            raise DictationError('Microphone unavailable. You can still type your custom prompt.') from None

    def _read(self):
        block = (C.c_ubyte*65536)()
        try:
            while True:
                available = self.sdl.SDL_GetQueuedAudioSize(self.device)
                count = min(available, len(block), MAX_PCM-len(self.pcm))
                count -= count % 2
                if count:
                    read = self.sdl.SDL_DequeueAudio(self.device, block, count)
                    if read > count or read % 2:
                        raise ValueError()
                    chunk = memoryview(block).cast('B')[:read]
                    self.level = signal_peak(chunk)
                    self.pcm.extend(chunk)
                    C.memset(block, 0, len(block))
                if len(self.pcm) >= MAX_PCM or self.seconds >= MAX_SECONDS:
                    self.limited = True
                    wipe(self.pcm)
                    break
                if self.stop_event.is_set():
                    # Drena o trecho já capturado; o dispositivo é fechado logo após.
                    if not count or available <= count:
                        break
                self.stop_event.wait(0.02)
        except Exception:
            self.error = 'Microphone capture failed. The draft was preserved; you can still type.'
            wipe(self.pcm)
        finally:
            C.memset(block, 0, len(block))
            self._release()

    def _release(self):
        if self.device:
            self.sdl.SDL_PauseAudioDevice(self.device, 1)
            self.sdl.SDL_ClearQueuedAudio(self.device)
            self.sdl.SDL_CloseAudioDevice(self.device)
            self.device = 0
        if self.initialized:
            self.sdl.SDL_QuitSubSystem(0x10)
            self.initialized = False

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        if self.active:
            raise DictationError('Microphone is still stopping. Try again shortly.')

    def take(self):
        self.stop()
        if self.error:
            raise DictationError(self.error)
        if not self.pcm:
            raise DictationError(NO_AUDIO)
        result, self.pcm = self.pcm, bytearray()
        return result

    def cancel(self):
        self.stop()
        wipe(self.pcm)


def multipart(pcm):
    if not isinstance(pcm, bytearray) or not 2 <= len(pcm) <= MAX_PCM or len(pcm) % 2:
        raise DictationError('No usable audio. Record again or type your custom prompt.')
    boundary = 'om-dictation-'+uuid.uuid4().hex
    body = bytearray()
    for name, value in (('model', MODEL), ('languages[]', 'pt'), ('response_format', 'json')):
        body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode())
    body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="dictation.wav"\r\n'
                 'Content-Type: audio/wav\r\n\r\n').encode())
    body.extend(struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36+len(pcm), b'WAVE', b'fmt ',
        16, 1, 1, SAMPLE_RATE, SAMPLE_RATE*2, 2, 16, b'data', len(pcm)))
    body.extend(pcm)
    body.extend(('\r\n--'+boundary+'--\r\n').encode())
    return body, 'multipart/form-data; boundary='+boundary


def request(body, content_type, key):
    req = urllib.request.Request(ENDPOINT, data=body, method='POST',
        headers={'Content-Type': content_type, 'Authorization': 'Bearer '+api_credentials.validate(key)})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE+1)
        if len(raw) > MAX_RESPONSE:
            raise DictationError('Transcription response is too large. Type or record a shorter prompt.')
        return json.loads(raw)
    except urllib.error.HTTPError as error:
        code, reason, parameter = error.code, None, None
        try:
            # Não exibir message, headers ou corpo; eles podem conter texto privado.
            raw = error.read(MAX_RESPONSE+1)
            if len(raw) <= MAX_RESPONSE:
                document = json.loads(raw)
                detail = document.get('error') if isinstance(document, dict) else None
                if isinstance(detail, dict):
                    candidate = detail.get('code')
                    reason = API_ERRORS.get(candidate) if isinstance(candidate, str) else None
                    candidate = detail.get('param')
                    parameter = candidate if isinstance(candidate, str) and candidate in PARAMETERS else None
        except (OSError, ValueError, UnicodeError):
            pass
        finally:
            error.close()
        raise DictationError(reason or FAILURE, http_status=code, parameter=parameter) from None
    except urllib.error.URLError as error:
        raise DictationError(TLS_FAILURE if isinstance(error.reason, ssl.SSLError) else NETWORK_FAILURE) from None
    except ssl.SSLError:
        raise DictationError(TLS_FAILURE) from None
    except (OSError, socket.timeout):
        raise DictationError(NETWORK_FAILURE) from None
    except (ValueError, UnicodeError):
        raise DictationError(FAILURE) from None


def transcribe(pcm, key, *, settings, transport=None, cancelled=None):
    """Consome e descarta o buffer em todos os desfechos, inclusive antes da rede."""
    body = None
    try:
        settings = ai_preferences.clean(settings)
        if not settings['voice_enabled'] or not settings['use_generation_key']:
            raise DictationError('Enable remote dictation and API key reuse before recording.')
        key = api_credentials.validate(key)
        if cancelled is not None and cancelled.is_set():
            return None
        body, content_type = multipart(pcm)
        if not signal_peak(pcm):
            raise DictationError(SILENT_AUDIO)
        wipe(pcm)
        if cancelled is not None and cancelled.is_set():
            return None
        response = (transport or request)(body, content_type, key)
        if cancelled is not None and cancelled.is_set():
            return None
        if not isinstance(response, dict) or not isinstance(response.get('text'), str):
            raise DictationError(BAD_RESPONSE)
        text = response['text']
        if not text.strip():
            raise DictationError('No speech was transcribed. The draft was preserved.')
        try:
            ai_preferences.clean(dict(text=text))
        except ValueError:
            raise DictationError('Transcript exceeds 8 KiB. Draft kept; no text was cut.') from None
        return text.strip()
    finally:
        wipe(pcm)
        wipe(body)
