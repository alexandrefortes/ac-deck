"""Sorteio, formato e ciclo do áudio de vitória sem saída física."""
import ctypes as C
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call, patch
import wave

from src.launcher import rogue_victory_music as music
from src.launcher.dictation import AudioSpec


class VictoryResultTests(unittest.TestCase):
    def test_only_a_fresh_armed_result_can_play_once(self):
        playback = music.Playback(Path('unused'))
        with patch.object(playback, 'play', side_effect=(False, True)) as play:
            self.assertFalse(playback.show_result('old-win'))
            playback.arm_result('new-win')
            self.assertFalse(playback.show_result('loss'))
            play.assert_not_called()
            self.assertFalse(playback.show_result('new-win'))
            self.assertFalse(playback.show_result('new-win'))
            play.assert_called_once_with()
            playback.arm_result('another-win')
            self.assertTrue(playback.show_result('another-win'))
            playback.arm_result('new-win')
            self.assertFalse(playback.show_result('new-win'))
            self.assertEqual(2, play.call_count)

    def test_new_transition_can_clear_an_unshown_win(self):
        playback = music.Playback(Path('unused'))
        with patch.object(playback, 'play') as play:
            playback.arm_result('win')
            playback.arm_result(None)
            self.assertFalse(playback.show_result('win'))
            play.assert_not_called()


class VictoryPlaybackTests(unittest.TestCase):
    def setUp(self):
        area = TemporaryDirectory(prefix='rogue-victory-')
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name) / 'victory music'
        self.playback = music.Playback(self.folder)
        self.sdl = Mock()
        self.sdl.SDL_InitSubSystem.return_value = 0
        self.sdl.SDL_OpenAudioDevice.side_effect = self.open_device
        self.sdl.SDL_MixAudioFormat.side_effect = self.mix
        self.sdl.SDL_QueueAudio.side_effect = self.queue
        self.queued = []
        self.playback.bind(self.sdl)

    def put(self, name, pcm=b'\x11\x22', *, channels=1, rate=44100):
        self.folder.mkdir(exist_ok=True)
        path = self.folder / name
        with wave.open(str(path), 'wb') as target:
            target.setparams((channels, 2, rate, 0, 'NONE', 'not compressed'))
            target.writeframes(pcm)
        return path

    def open_device(self, name, is_capture, wanted, actual, allowed_changes):
        self.assertEqual((None, 0, 0), (name, is_capture, allowed_changes))
        wanted, actual = (C.cast(value, C.POINTER(AudioSpec)) for value in (wanted, actual))
        self.assertEqual((44100, 0x8010, 1), (wanted[0].freq, wanted[0].format, wanted[0].channels))
        actual[0] = wanted[0]
        return 2

    def mix(self, output, pcm, format_id, length, volume):
        self.assertEqual((0x8010, len(pcm), 70), (format_id, length, volume))
        C.memmove(output, pcm, length)

    def queue(self, device, pcm, length):
        self.assertEqual(2, device)
        self.queued.append(C.string_at(pcm, length))
        return 0

    def test_missing_or_incompatible_tracks_do_not_open_audio(self):
        self.assertFalse(self.playback.play())
        self.put('you-win-street-fighter.wav')
        self.put('doom-intermission-sc55.ogg')
        self.put(music.TRACKS[0].upper())
        self.put(music.TRACKS[1], channels=2)
        self.put(music.TRACKS[2], rate=48000)
        (self.folder / music.TRACKS[3]).write_bytes(b'invalid WAV data')
        self.assertFalse(self.playback.play())
        self.sdl.SDL_InitSubSystem.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'Links and FIFOs require Linux in this fixture')
    def test_links_and_nonregular_entries_are_excluded(self):
        original = self.put('original.wav')
        (self.folder / music.TRACKS[0]).symlink_to(original)
        (self.folder / music.TRACKS[1]).mkdir()
        os.link(original, self.folder / music.TRACKS[2])
        os.mkfifo(self.folder / music.TRACKS[3])
        self.assertFalse(self.playback.play())
        self.sdl.SDL_OpenAudioDevice.assert_not_called()

    def test_game_and_launcher_draw_independently_and_close_each_device(self):
        tracks = (
            'doom-intermission-sc55.wav',
            'smb-course-clear-fanfare.wav',
            'sfii-victory-screen-arcade.wav',
            'mk64-finish-line.wav',
        )
        payloads = [bytes((index, index)) for index in range(len(tracks))]
        for name, pcm in zip(tracks, payloads):
            self.put(name, pcm)
        picks = iter((0, 0, 3))

        def choose(candidates):
            self.assertEqual(4, len(candidates))
            return candidates[next(picks)]

        with patch.object(music.secrets, 'choice', side_effect=choose) as draw:
            self.assertTrue(self.playback.play())
            self.playback.arm_result('win')
            self.assertTrue(self.playback.show_result('win'))
            self.assertFalse(self.playback.show_result('win'))
            self.playback.stop()
            self.assertTrue(self.playback.play())
            self.playback.stop()
            self.playback.stop()

        self.assertEqual([payloads[0], payloads[0], payloads[3]], self.queued)
        self.assertEqual(3, draw.call_count)
        self.assertEqual([call(2, 0), call(2, 1)] * 3, self.sdl.SDL_PauseAudioDevice.call_args_list)
        self.assertEqual([call(2)] * 3, self.sdl.SDL_ClearQueuedAudio.call_args_list)
        self.assertEqual([call(2)] * 3, self.sdl.SDL_CloseAudioDevice.call_args_list)
        self.assertEqual([call(0x10)] * 3, self.sdl.SDL_InitSubSystem.call_args_list)
        self.assertEqual([call(0x10)] * 3, self.sdl.SDL_QuitSubSystem.call_args_list)

    def test_incomplete_track_does_not_queue_partial_audio(self):
        path = self.put(music.TRACKS[0], pcm=b'\x01\x02' * 4)
        path.write_bytes(path.read_bytes()[:-2])
        self.assertFalse(self.playback.play())
        self.sdl.SDL_InitSubSystem.assert_not_called()

    def test_audio_init_or_open_failure_is_silent_and_balanced(self):
        self.put(music.TRACKS[0])
        self.sdl.SDL_InitSubSystem.return_value = -1
        self.assertFalse(self.playback.play())
        self.sdl.SDL_QuitSubSystem.assert_not_called()
        self.sdl.SDL_OpenAudioDevice.assert_not_called()

        self.sdl.SDL_InitSubSystem.return_value = 0
        self.sdl.SDL_OpenAudioDevice.side_effect = None
        self.sdl.SDL_OpenAudioDevice.return_value = 0
        self.assertFalse(self.playback.play())
        self.sdl.SDL_QuitSubSystem.assert_called_once_with(0x10)
        self.sdl.SDL_CloseAudioDevice.assert_not_called()

    def test_queue_failure_closes_the_paused_device_and_never_starts(self):
        self.put(music.TRACKS[0])
        self.sdl.SDL_QueueAudio.side_effect = None
        self.sdl.SDL_QueueAudio.return_value = -1
        self.assertFalse(self.playback.play())
        self.sdl.SDL_PauseAudioDevice.assert_called_once_with(2, 1)
        self.sdl.SDL_ClearQueuedAudio.assert_called_once_with(2)
        self.sdl.SDL_CloseAudioDevice.assert_called_once_with(2)
        self.sdl.SDL_QuitSubSystem.assert_called_once_with(0x10)


if __name__ == '__main__':
    unittest.main()
