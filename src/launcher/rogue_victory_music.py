"""Reproduz as faixas PCM de vitória pelo SDL2 do launcher."""
from contextlib import ExitStack
import ctypes as C
from pathlib import Path
import secrets
import wave

from . import file_io as safe
from .dictation import AudioSpec


TRACKS = (
    'doom-intermission-sc55.wav',
    'smb-course-clear-fanfare.wav',
    'sfii-victory-screen-arcade.wav',
    'mk64-finish-line.wav',
)
_AUDIO = 0x10
_S16LE = 0x8010
_RATE = 44100
_MAX_BYTES = 32 * 1024 * 1024
_VOLUME = 70  # SDL_MIX_MAXVOLUME is 128, roughly the original 55% gain.


class Playback:
    def __init__(self, folder: Path):
        self.folder = folder
        self._sdl = None
        self._device = 0
        self._initialized = False
        self._armed_result = None
        self._shown_results = set()

    def bind(self, sdl):
        self._sdl = sdl

    def _bind_functions(self):
        pointer, integer, unsigned = C.c_void_p, C.c_int, C.c_uint32
        spec = C.POINTER(AudioSpec)
        signatures = {
            'SDL_InitSubSystem': (integer, [unsigned]),
            'SDL_QuitSubSystem': (None, [unsigned]),
            'SDL_OpenAudioDevice': (unsigned, [C.c_char_p, integer, spec, spec, integer]),
            'SDL_MixAudioFormat': (None, [pointer, pointer, C.c_uint16, unsigned, integer]),
            'SDL_QueueAudio': (integer, [unsigned, pointer, unsigned]),
            'SDL_PauseAudioDevice': (None, [unsigned, integer]),
            'SDL_ClearQueuedAudio': (None, [unsigned]),
            'SDL_CloseAudioDevice': (None, [unsigned]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self._sdl, name)
            function.restype, function.argtypes = result, args

    def _read_pcm(self):
        try:
            folder = safe.absolute(self.folder)
            safe.check_components(folder)
            names = {path.name for path in folder.iterdir() if path.name in TRACKS}
        except (OSError, safe.SafetyError):
            return None

        with ExitStack() as files:
            tracks = []
            for name in TRACKS:
                if name not in names:
                    continue
                try:
                    stream, info = safe.open_reference(folder / name)
                    files.enter_context(stream)
                    if not 44 < info.st_size <= _MAX_BYTES:
                        continue
                    source = files.enter_context(wave.open(stream, 'rb'))
                    if ((source.getframerate(), source.getnchannels(), source.getsampwidth(),
                         source.getcomptype()) == (_RATE, 1, 2, 'NONE')
                            and 0 < source.getnframes() * 2 <= info.st_size - 44):
                        tracks.append(source)
                except (OSError, EOFError, wave.Error, safe.SafetyError):
                    continue
            if not tracks:
                return None
            source = secrets.choice(tracks)
            frames = source.getnframes()
            try:
                pcm = source.readframes(frames)
            except (OSError, EOFError, wave.Error):
                return None
            return pcm if len(pcm) == frames * 2 else None

    def play(self):
        self.stop()
        sdl = self._sdl
        if sdl is None:
            return False
        pcm = self._read_pcm()
        if pcm is None:
            return False
        try:
            self._bind_functions()
        except AttributeError:
            return False
        if sdl.SDL_InitSubSystem(_AUDIO) != 0:
            return False
        self._initialized = True
        started = False
        try:
            wanted = AudioSpec(freq=_RATE, format=_S16LE, channels=1, samples=1024)
            actual = AudioSpec()
            self._device = sdl.SDL_OpenAudioDevice(None, 0, C.byref(wanted), C.byref(actual), 0)
            if not self._device or (actual.freq, actual.format, actual.channels) != (_RATE, _S16LE, 1):
                return False
            samples = C.create_string_buffer(len(pcm))
            sdl.SDL_MixAudioFormat(samples, pcm, _S16LE, len(pcm), _VOLUME)
            if sdl.SDL_QueueAudio(self._device, samples, len(pcm)) != 0:
                return False
            sdl.SDL_PauseAudioDevice(self._device, 0)
            started = True
            return True
        finally:
            if not started:
                self.stop()

    def stop(self):
        if self._device:
            self._sdl.SDL_PauseAudioDevice(self._device, 1)
            self._sdl.SDL_ClearQueuedAudio(self._device)
            self._sdl.SDL_CloseAudioDevice(self._device)
            self._device = 0
        if self._initialized:
            self._sdl.SDL_QuitSubSystem(_AUDIO)
            self._initialized = False

    def arm_result(self, attempt_id):
        self._armed_result = None
        if isinstance(attempt_id, str) and attempt_id and attempt_id not in self._shown_results:
            self._armed_result = attempt_id

    def show_result(self, attempt_id):
        if self._armed_result is None or attempt_id != self._armed_result:
            return False
        self._armed_result = None
        self._shown_results.add(attempt_id)
        return self.play()
