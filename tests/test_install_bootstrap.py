"""Tests only synthetic archives and mocked setup; no network or launcher."""
import hashlib
import io
import os
from pathlib import Path
import select
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import MagicMock, mock_open, patch

from scripts import install_ac_deck as bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'synthetic.tar.gz'
        self.destination = self.root / 'new installation'

    def make_archive(self, extras=()):
        with tarfile.open(self.archive, 'w:gz') as tar:
            for name, data, kind in [('ac-deck-linux-x86_64/ac-deck', b'synthetic', 'file'), *extras]:
                info = tarfile.TarInfo(name)
                info.mode = 0o755
                if kind == 'file':
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
                elif kind == 'symlink':
                    info.type, info.linkname = tarfile.SYMTYPE, data
                    tar.addfile(info)
                elif kind == 'hardlink':
                    info.type, info.linkname = tarfile.LNKTYPE, data
                    tar.addfile(info)
        return hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_verified_archive_installs_without_executing(self):
        digest = self.make_archive([('ac-deck-linux-x86_64/_internal/data.txt', b'data', 'file')])
        with patch.object(bootstrap.subprocess, 'run') as run:
            result = bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
        run.assert_not_called()
        self.assertEqual(result, self.destination)
        self.assertEqual((result / 'ac-deck').read_bytes(), b'synthetic')
        self.assertEqual((result / '_internal/data.txt').read_bytes(), b'data')

    def test_hash_mismatch_stops_before_extraction_or_setup(self):
        self.make_archive()
        with patch.object(bootstrap, '_extract_archive') as extract, patch.object(bootstrap, '_run_setup') as run:
            with self.assertRaisesRegex(bootstrap.InstallError, 'SHA-256'):
                bootstrap.install(archive=self.archive, sha256='0' * 64,
                                  destination=self.destination, run_setup=True)
        extract.assert_not_called()
        run.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_existing_destination_is_preserved_even_if_empty(self):
        digest = self.make_archive()
        self.destination.mkdir()
        sentinel = self.destination / 'user.txt'
        sentinel.write_text('keep')
        with self.assertRaisesRegex(bootstrap.InstallError, 'already exists'):
            bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.assertEqual(list(self.destination.iterdir()), [sentinel])

    def test_verified_existing_payload_reruns_setup_preserving_player_files(self):
        digest = self.make_archive([('ac-deck-linux-x86_64/_internal/data.txt', b'data', 'file')])
        bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
        local = self.destination / 'local'
        local.mkdir()
        progress = local / 'progress.json'
        progress.write_bytes(b'newer player progress')
        unchanged = (self.destination / 'ac-deck').stat().st_mtime_ns
        with patch.object(bootstrap, '_publish') as publish, \
             patch.object(bootstrap, '_run_setup') as setup:
            bootstrap.install(archive=self.archive, sha256=digest,
                              destination=self.destination, reuse_verified=True, run_setup=True)
        publish.assert_not_called()
        setup.assert_called_once_with(self.destination)
        self.assertEqual(progress.read_bytes(), b'newer player progress')
        self.assertEqual((self.destination / 'ac-deck').stat().st_mtime_ns, unchanged)

    def test_reuse_refuses_changed_or_missing_distribution_files(self):
        digest = self.make_archive([('ac-deck-linux-x86_64/_internal/data.txt', b'data', 'file')])
        bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
        library = self.destination / '_internal/data.txt'
        library.write_bytes(b'player replacement')
        with patch.object(bootstrap, '_run_setup') as setup:
            with self.assertRaisesRegex(bootstrap.InstallError, 'differs from this version'):
                bootstrap.install(archive=self.archive, sha256=digest,
                                  destination=self.destination, reuse_verified=True, run_setup=True)
            self.assertEqual(library.read_bytes(), b'player replacement')
            library.unlink()
            with self.assertRaisesRegex(bootstrap.InstallError, 'incomplete'):
                bootstrap.install(archive=self.archive, sha256=digest,
                                  destination=self.destination, reuse_verified=True, run_setup=True)
        setup.assert_not_called()

    def test_reuse_does_not_adopt_an_empty_existing_directory(self):
        digest = self.make_archive()
        self.destination.mkdir()
        with self.assertRaisesRegex(bootstrap.InstallError, 'incomplete'):
            bootstrap.install(archive=self.archive, sha256=digest,
                              destination=self.destination, reuse_verified=True)
        self.assertEqual(list(self.destination.iterdir()), [])

    @unittest.skipUnless(os.name == 'posix', 'Requires POSIX file modes')
    def test_reuse_refuses_changed_permissions_even_with_identical_bytes(self):
        digest = self.make_archive([('ac-deck-linux-x86_64/_internal/data.txt', b'data', 'file')])
        bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
        path = self.destination / '_internal/data.txt'
        original_mode = path.stat().st_mode & 0o777
        path.chmod(0o777)
        with patch.object(bootstrap, '_run_setup') as setup:
            with self.assertRaisesRegex(bootstrap.InstallError, 'differs from this version'):
                bootstrap.install(archive=self.archive, sha256=digest,
                                  destination=self.destination, reuse_verified=True, run_setup=True)
        setup.assert_not_called()
        self.assertEqual(path.read_bytes(), b'data')
        self.assertNotEqual(original_mode, path.stat().st_mode & 0o777)

    def test_reuse_refuses_symlink_to_identical_distribution_file(self):
        digest = self.make_archive()
        bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
        executable = self.destination / 'ac-deck'
        real = self.root / 'real executable'
        executable.replace(real)
        try:
            executable.symlink_to(real)
        except OSError as error:
            self.skipTest(f'Cannot create symlink fixture: {error}')
        with patch.object(bootstrap, '_run_setup') as setup:
            with self.assertRaisesRegex(bootstrap.InstallError, 'Symbolic links'):
                bootstrap.install(archive=self.archive, sha256=digest,
                                  destination=self.destination, reuse_verified=True, run_setup=True)
        setup.assert_not_called()
        self.assertEqual(real.read_bytes(), b'synthetic')

    def test_archive_links_paths_and_duplicates_are_rejected_before_install(self):
        cases = [('../outside', b'evil', 'file'),
                 ('ac-deck-linux-x86_64/../outside', b'evil', 'file'),
                 ('ac-deck-linux-x86_64/link', '../outside', 'symlink'),
                 ('ac-deck-linux-x86_64/link', 'ac-deck-linux-x86_64/ac-deck', 'hardlink'),
                 ('ac-deck-linux-x86_64/ac-deck', b'overwrite', 'file')]
        for entry in cases:
            with self.subTest(entry=entry):
                digest = self.make_archive([entry])
                with self.assertRaises(bootstrap.InstallError):
                    bootstrap.install(archive=self.archive, sha256=digest, destination=self.destination)
                self.assertFalse(self.destination.exists())
                self.assertFalse((self.root / 'outside').exists())

    def test_setup_runs_only_when_selected_after_install(self):
        digest = self.make_archive()
        with patch.object(bootstrap.sys.stdin, 'isatty', return_value=True), \
             patch.object(bootstrap.subprocess, 'run') as run:
            bootstrap.install(archive=self.archive, sha256=digest,
                              destination=self.destination, run_setup=True)
        run.assert_called_once_with([str(self.destination / 'ac-deck'), 'install'], check=True)

    def test_modified_published_bytes_prevent_execution(self):
        digest = self.make_archive()
        publish = bootstrap._publish

        def tamper(stage, destination):
            publish(stage, destination)
            (destination / 'ac-deck').write_bytes(b'altered')

        with patch.object(bootstrap, '_publish', side_effect=tamper), \
             patch.object(bootstrap, '_run_setup') as run:
            with self.assertRaisesRegex(bootstrap.InstallError, 'differ from the verified archive'):
                bootstrap.install(archive=self.archive, sha256=digest,
                                  destination=self.destination, run_setup=True)
        run.assert_not_called()
        self.assertEqual((self.destination / 'ac-deck').read_bytes(), b'altered')

    def test_hardlinked_published_file_prevents_execution(self):
        digest = self.make_archive()
        publish = bootstrap._publish

        def link(stage, destination):
            publish(stage, destination)
            try:
                os.link(destination / 'ac-deck', self.root / 'linked')
            except OSError as error:
                self.skipTest(f'Cannot create hardlink fixture: {error}')

        with patch.object(bootstrap, '_publish', side_effect=link), \
             patch.object(bootstrap, '_run_setup') as run:
            with self.assertRaisesRegex(bootstrap.InstallError, 'independent regular file'):
                bootstrap.install(archive=self.archive, sha256=digest,
                                  destination=self.destination, run_setup=True)
        run.assert_not_called()

    def test_piped_setup_uses_controlling_terminal(self):
        tty = mock_open()
        with patch.object(bootstrap.sys.stdin, 'isatty', return_value=False), \
             patch('builtins.open', tty), patch.object(bootstrap.subprocess, 'run') as run:
            bootstrap._run_setup(self.destination)
        tty.assert_called_once_with('/dev/tty', 'r+', encoding='utf-8')
        self.assertIs(run.call_args.kwargs['stdin'], tty.return_value.__enter__.return_value)
        self.assertIs(run.call_args.kwargs['stdout'], tty.return_value.__enter__.return_value)
        self.assertIs(run.call_args.kwargs['stderr'], tty.return_value.__enter__.return_value)

    def test_setup_without_terminal_is_not_started(self):
        with patch.object(bootstrap.sys.stdin, 'isatty', return_value=False), \
             patch('builtins.open', side_effect=OSError('no terminal')), \
             patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaisesRegex(bootstrap.InstallError, 'needs a terminal'):
                bootstrap._run_setup(self.destination)
        run.assert_not_called()

    def test_partial_publish_is_reported_and_preserved(self):
        stage = self.root / 'stage'
        stage.mkdir()
        (stage / 'ac-deck').write_bytes(b'synthetic')
        with patch.object(bootstrap.shutil, 'copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(bootstrap.InstallError, 'partial directory was preserved'):
                bootstrap._publish(stage, self.destination)
        self.assertTrue(self.destination.is_dir())
        self.assertTrue((self.destination / 'ac-deck').exists())

    def test_url_must_be_explicit_https_and_download_hash_matches(self):
        self.make_archive()
        data = self.archive.read_bytes()
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [data, b'']
        response.geturl.return_value = 'https://downloads.example/release.tar.gz'
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(bootstrap.urllib.request, 'build_opener', return_value=opener):
            bootstrap.install(url='https://downloads.example/release.tar.gz',
                              sha256=hashlib.sha256(data).hexdigest(), destination=self.destination)
        self.assertEqual((self.destination / 'ac-deck').read_bytes(), b'synthetic')
        with self.assertRaises(bootstrap.InstallError):
            bootstrap._https_url('http://downloads.example/release.tar.gz')
        with self.assertRaises(bootstrap.InstallError):
            bootstrap._https_url('https://user:secret@downloads.example/release.tar.gz')

    def test_default_xdg_directory_and_invalid_input(self):
        digest = self.make_archive()
        with patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root / 'xdg')}):
            result = bootstrap.install(archive=self.archive, sha256=digest)
        self.assertEqual(result, self.root / 'xdg/ac-deck')
        with self.assertRaises(bootstrap.InstallError):
            bootstrap.install(sha256='0' * 64, destination=self.root / 'absent')
        with self.assertRaises(bootstrap.InstallError):
            bootstrap.install(archive=self.archive, sha256='no', destination=self.root / 'absent')


    def test_cli_refusal_precedes_directories_staging_and_downloads(self):
        destination = self.root / 'absent parent' / 'installation'
        with patch.object(bootstrap, '_confirm_terms', return_value=False), \
             patch.object(bootstrap, '_mkdir_parents') as mkdir, \
             patch.object(bootstrap, '_stage_archive') as download, \
             patch.object(bootstrap.tempfile, 'TemporaryDirectory') as stage, \
             patch.object(bootstrap.sys, 'stderr', io.StringIO()):
            result = bootstrap.main(['--url', 'https://downloads.example/runtime.tar.gz',
                                     '--sha256', '0' * 64, '--destination', str(destination)])
        self.assertNotEqual(result, 0)
        mkdir.assert_not_called()
        download.assert_not_called()
        stage.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_asks_with_or_without_setup_and_explicit_flag_bypasses_terminal(self):
        for extra in ([], ['--run-setup'], ['--accept-terms']):
            with self.subTest(extra=extra), \
                 patch.object(bootstrap, '_confirm_terms', return_value=True) as confirm, \
                 patch.object(bootstrap, 'install', return_value=self.destination) as install, \
                 patch.object(bootstrap.sys, 'stdout', io.StringIO()):
                result = bootstrap.main(['--archive', str(self.archive), '--sha256', '0' * 64, *extra])
            self.assertEqual(result, 0)
            install.assert_called_once()
            self.assertEqual(install.call_args.kwargs['run_setup'], '--run-setup' in extra)
            self.assertEqual(confirm.call_count, 0 if '--accept-terms' in extra else 1)

    def test_cli_interrupt_and_eof_cancel_without_installing(self):
        for error in (KeyboardInterrupt, EOFError):
            with self.subTest(error=error), \
                 patch.object(bootstrap, '_confirm_terms', side_effect=error), \
                 patch.object(bootstrap, 'install') as install, \
                 patch.object(bootstrap.sys, 'stderr', io.StringIO()):
                result = bootstrap.main(['--archive', str(self.archive), '--sha256', '0' * 64])
            self.assertNotEqual(result, 0)
            install.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])


class BootstrapTermsTests(unittest.TestCase):
    def test_selection_and_confirmation_keys(self):
        self.assertEqual(bootstrap._terms_event(b'\r', False, 14), (False, False))
        for key in (b'\x1b[A', b'\x1b[D', b'\x1bOA', b'\x1bOD'):
            self.assertEqual(bootstrap._terms_event(key, False, 14), (True, None))
        for key in (b'\x1b[B', b'\x1b[C', b'\x1bOB', b'\x1bOC'):
            self.assertEqual(bootstrap._terms_event(key, True, 14), (False, None))
        self.assertEqual(bootstrap._terms_event(b'\t', False, 14), (True, None))
        self.assertEqual(bootstrap._terms_event(b'\r', True, 14), (True, True))
        for key in (b'y', b'Y'):
            self.assertEqual(bootstrap._terms_event(key, False, 14), (False, True))
        for key in (b'n', b'N', b'\x1b'):
            self.assertEqual(bootstrap._terms_event(key, True, 14), (True, False))
        self.assertEqual(bootstrap._terms_event(b'?', True, 14), (True, None))

    def test_mouse_accepts_only_left_press_on_visible_buttons(self):
        self.assertEqual(bootstrap._terms_event(b'\x1b[<0;2;14M', False, 14), (False, True))
        self.assertEqual(bootstrap._terms_event(b'\x1b[<0;13;14M', True, 14), (True, False))
        for key in (b'\x1b[<0;2;13M', b'\x1b[<0;9;14M', b'\x1b[<0;2;14m',
                    b'\x1b[<2;2;14M', b'\x1b[<32;2;14M', b'\x1b[<64;2;14M'):
            self.assertEqual(bootstrap._terms_event(key, False, 14), (False, None))

    def test_escape_sequences_are_read_across_separate_terminal_reads(self):
        sequence = b'\x1b[<0;2;14M'
        with patch.object(bootstrap.os, 'read', side_effect=[bytes([b]) for b in sequence]), \
             patch.object(bootstrap.select, 'select', return_value=([9], [], [])):
            self.assertEqual(bootstrap._read_terms_key(9), sequence)
        with patch.object(bootstrap.os, 'read', return_value=b'\x1b'), \
             patch.object(bootstrap.select, 'select', return_value=([], [], [])):
            self.assertEqual(bootstrap._read_terms_key(9), b'\x1b')

    @unittest.skipUnless(os.name == 'posix', 'Linux controlling terminal')
    def test_no_controlling_terminal_does_not_read_piped_stdin(self):
        with patch.object(bootstrap.os, 'open', side_effect=OSError('no terminal')) as opened, \
             patch.object(bootstrap.sys.stdin, 'read', side_effect=AssertionError('stdin consumed')):
            with self.assertRaisesRegex(bootstrap.InstallError, 'Terms need a terminal'):
                bootstrap._confirm_terms()
        self.assertEqual(opened.call_args.args[0], '/dev/tty')

    def terminal_cli(self, response):
        import fcntl
        import pty
        import termios
        import struct

        master, slave = pty.openpty()
        process = None
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
            previous = termios.tcgetattr(slave)
            root = str(Path(bootstrap.__file__).resolve().parents[1])
            code = (f'import sys;sys.path.insert(0,{root!r});'
                    'from pathlib import Path;from scripts import install_ac_deck as b;'
                    'b.install=lambda **kwargs:Path("/synthetic-installation");'
                    'status=b.main(["--url","https://downloads.example/runtime.tar.gz",'
                    '"--sha256","0"*64]);'
                    'print("UNREAD_STDIN="+sys.stdin.read());raise SystemExit(status)')
            def session():
                os.setsid()
                fcntl.ioctl(1, termios.TIOCSCTTY, 0)
            process = subprocess.Popen([sys.executable, '-B', '-c', code], stdin=subprocess.PIPE,
                                       stdout=slave, stderr=slave, preexec_fn=session)
            process.stdin.write(b'piped code stays unread')
            process.stdin.close()
            output = b''
            deadline = time.monotonic() + 15
            while b'[ No ]' not in output and time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    output += os.read(master, 65536)
            self.assertIn(b'[ No ]', output, output.decode(errors='replace'))
            row = output.count(b'\n') + 1
            os.write(master, response(row) if callable(response) else response)
            process.wait(timeout=10)
            while select.select([master], [], [], 0)[0]:
                output += os.read(master, 65536)
            self.assertEqual(termios.tcgetattr(slave), previous)
            self.assertIn(bootstrap._TERMS_LEAVE.encode(), output)
            self.assertIn(b'UNREAD_STDIN=piped code stays unread', output)
            return process.returncode, output
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)

    @unittest.skipUnless(os.name == 'posix', 'Linux controlling terminal')
    def test_real_terminal_keyboard_defaults_interrupts_and_cleanup_with_piped_stdin(self):
        for response, accepted in ((b'\r', False), (b'\x1b[D\r', True), (b'\x1b[A\r', True),
                                   (b'\x1b[D\x1b[C\r', False), (b'\x1b[A\x1b[B\r', False),
                                   (b'\x03', False), (b'\x04', False), (b'\x1b', False)):
            with self.subTest(response=response):
                result, output = self.terminal_cli(response)
                self.assertEqual(result, 0 if accepted else 1, output.decode(errors='replace'))

    @unittest.skipUnless(os.name == 'posix', 'Linux controlling terminal')
    def test_real_terminal_sgr_mouse_clicks(self):
        for column, accepted in ((2, True), (13, False)):
            with self.subTest(column=column):
                result, output = self.terminal_cli(lambda row: f'\x1b[<0;{column};{row}M'.encode())
                self.assertEqual(result, 0 if accepted else 1, output.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
