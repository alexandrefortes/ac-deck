from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.launcher import community_install, steam_install_options


class CommunityInstallTests(unittest.TestCase):
    def test_wrong_csp_version_stops_before_downloading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, game = Path(temporary), Path(temporary) / 'game'
            game.mkdir()
            with patch.object(community_install.install_discovery, 'validate_game', return_value=game), \
                    patch.object(community_install.csp, 'VERSION', '0.3.0'), \
                    patch.object(community_install.community_download, 'download') as download:
                with self.assertRaisesRegex(ValueError, '0.3.1'):
                    community_install.prepare(root, game)
                download.assert_not_called()

    def test_download_and_verify_kit_before_attaching_game(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, game = Path(temporary), Path(temporary) / 'game'
            game.mkdir()
            calls = []

            def download(url, archive, digest):
                calls.append('download')
                archive.write_bytes(b'fixture')

            def unpack(archive, kit):
                calls.append('unpack')
                kit.mkdir()

            def verify(kit, archive):
                calls.append('verify')

            def attach(source, batch, *, project_root):
                calls.append('attach')
                return project_root / 'local/work/community'

            with patch.object(community_install.install_discovery, 'validate_game', return_value=game), \
                    patch.object(community_install.csp, 'VERSION', '0.3.1'), \
                    patch.object(community_install.community_download, 'download', side_effect=download), \
                    patch.object(community_install.csp, 'unpack', side_effect=unpack), \
                    patch.object(community_install, '_verify_kit', side_effect=verify), \
                    patch.object(community_install.installed, 'attach', side_effect=attach):
                result = community_install.prepare(root, game)
            self.assertEqual(['download', 'unpack', 'verify', 'attach'], calls)
            self.assertEqual(root / 'local/work/community', result)

    def test_invalid_kit_does_not_attach_or_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, game = Path(temporary), Path(temporary) / 'game'
            game.mkdir()
            (root / 'csp').mkdir()
            marker = root / 'csp/unknown'
            marker.write_text('preserve', encoding='utf-8')
            with patch.object(community_install.install_discovery, 'validate_game', return_value=game), \
                    patch.object(community_install.csp, 'VERSION', '0.3.1'), \
                    patch.object(community_install.installed, 'attach') as attach:
                with self.assertRaisesRegex(ValueError, 'no verified source archive'):
                    community_install.prepare(root, game)
                attach.assert_not_called()
            self.assertEqual('preserve', marker.read_text(encoding='utf-8'))

    def test_failed_download_stays_in_staging_and_retry_can_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, game = Path(temporary), Path(temporary) / 'game'
            game.mkdir()
            calls = 0

            def download(url, target, digest):
                nonlocal calls
                calls += 1
                target.write_bytes(b'partial' if calls == 1 else b'complete')
                if calls == 1:
                    raise OSError('interrupted download')

            with patch.object(community_install.install_discovery, 'validate_game', return_value=game), \
                    patch.object(community_install.community_download, 'download', side_effect=download), \
                    patch.object(community_install.csp, 'unpack', side_effect=lambda archive, target: target.mkdir()), \
                    patch.object(community_install, '_verify_kit'), \
                    patch.object(community_install.installed, 'attach', return_value=root / 'package'):
                with self.assertRaisesRegex(OSError, 'interrupted'):
                    community_install.prepare(root, game)
                self.assertFalse((root / 'local/csp-source.zip').exists())
                self.assertEqual([b'partial'], [path.read_bytes() for path in (root / 'local').glob('csp-source-*.zip')])
                community_install.prepare(root, game)
            self.assertEqual(b'complete', (root / 'local/csp-source.zip').read_bytes())
            self.assertTrue((root / 'csp').is_dir())

    def test_failed_extraction_keeps_final_kit_absent_and_retry_uses_new_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, game = Path(temporary), Path(temporary) / 'game'
            game.mkdir()
            archive = root / 'local/csp-source.zip'
            archive.parent.mkdir()
            archive.write_bytes(b'pinned')
            calls = 0

            def unpack(archive, target):
                nonlocal calls
                calls += 1
                target.mkdir()
                if calls == 1:
                    (target / 'partial').write_bytes(b'preserve')
                    raise OSError('interrupted extraction')

            with patch.object(community_install.install_discovery, 'validate_game', return_value=game), \
                    patch.object(community_install.csp, 'ARCHIVE_SHA256', hashlib.sha256(b'pinned').hexdigest()), \
                    patch.object(community_install.csp, 'unpack', side_effect=unpack), \
                    patch.object(community_install, '_verify_kit'), \
                    patch.object(community_install.installed, 'attach', return_value=root / 'package'):
                with self.assertRaisesRegex(OSError, 'interrupted'):
                    community_install.prepare(root, game)
                self.assertFalse((root / 'csp').exists())
                community_install.prepare(root, game)
            self.assertTrue((root / 'csp').is_dir())
            self.assertEqual([b'preserve'], [path.read_bytes() for path in (root / 'local').glob('csp-kit-*/partial')])

    def test_manual_path_is_available_when_no_game_is_found(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            with patch.object(community_install.install_discovery, 'discover', return_value=[]), \
                    patch.object(community_install.install_discovery, 'validate_game', return_value=path) as validate:
                result = community_install.choose_game(prompt=lambda _: str(path), output=lambda _: None)
            self.assertEqual(path, result)
            validate.assert_called_once_with(path)

    def test_preexisting_unowned_csp_is_reported_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game, package = root / 'game', root / 'package'
            game.mkdir()
            package.mkdir()
            proxy = game / 'dwrite.dll'
            proxy.write_bytes(b'player data')
            manifest = {'files': [{'path': 'dwrite.dll', 'sha256': hashlib.sha256(b'pinned').hexdigest()}]}
            with patch.object(community_install, '_verify_kit', return_value=manifest):
                with self.assertRaisesRegex(ValueError, 'differs'):
                    community_install.preflight_csp(root, game, package)
            self.assertEqual(b'player data', proxy.read_bytes())

    def test_kit_manifest_must_match_verified_archive_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'csp.zip'
            with zipfile.ZipFile(archive, 'w') as source:
                source.writestr('dwrite.dll', b'original')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            modified = hashlib.sha256(b'modified').hexdigest()
            forged = {'files': [{'path': 'dwrite.dll', 'sha256': modified, 'size_bytes': 8}]}
            with patch.object(community_install.csp, 'ARCHIVE_SHA256', digest), \
                    patch.object(community_install.csp, 'verify', return_value=forged):
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    community_install._verify_kit(root, archive)

    def test_changed_game_executable_blocks_reuse_of_attachment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game, package = root / 'game', root / 'package'
            game.mkdir()
            package.mkdir()
            (game / 'acs.exe').write_bytes(b'changed')
            record = {'kind': 'deck_installed_game', 'status': 'prepared',
                      'game_mode': 'installed', 'source': str(game),
                      'selection': [{'relative_path': 'acs.exe',
                                     'sha256': hashlib.sha256(b'old').hexdigest()}]}
            (package / 'prepared.json').write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'executable changed'):
                community_install.preflight_attachment(game, package)
            self.assertEqual(b'changed', (game / 'acs.exe').read_bytes())

    def test_installer_only_offers_accounts_from_a_root_declaring_selected_game(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'ac-deck').write_bytes(b'fixture')
            game, package = root / 'game', root / 'package'
            game.mkdir()
            package.mkdir()
            unrelated, matching = root / 'steam-a', root / 'steam-b'
            unrelated.mkdir()
            matching.mkdir()
            with patch.object(community_install, 'choose_game', return_value=game), \
                    patch.object(community_install, 'prepare', return_value=package), \
                    patch.object(community_install, 'preflight_attachment'), \
                    patch.object(community_install, 'preflight_csp'), \
                    patch.object(community_install, 'steam_roots', return_value=[unrelated, matching]), \
                    patch.object(community_install.install_discovery, 'discover_from_root',
                                 side_effect=lambda value: [game] if value == matching else []), \
                    patch.object(steam_install_options, 'discover_accounts', return_value=['123']), \
                    patch.object(steam_install_options, '_steam_closed'), \
                    patch.object(community_install.csp, 'install') as csp_install, \
                    patch.object(steam_install_options, 'install') as install:
                community_install._run_locked(root, prompt=lambda _: self.fail('Unexpected setup question'), output=lambda _: None)
            self.assertEqual(matching, install.call_args.args[0])
            self.assertEqual('123', install.call_args.args[1])
            csp_install.assert_called_once_with(root / 'csp', package)

    def test_running_steam_stops_before_discovery_or_preparation(self):
        with patch.object(steam_install_options, '_steam_closed',
                          side_effect=ValueError('Close Steam and run the same command again')), \
                patch.object(community_install, 'choose_game') as choose, \
                patch.object(community_install, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'same command'):
                community_install._run_locked(Path('.'), prompt=lambda _: self.fail('Unexpected setup question'), output=lambda _: None)
        choose.assert_not_called()
        prepare.assert_not_called()

    def test_setup_waits_for_the_player_to_close_steam_without_restarting_it(self):
        messages = []
        with patch.object(steam_install_options, '_steam_closed',
                          side_effect=[steam_install_options.ProcessesRunning('running'), None]) as check, \
                patch.object(community_install.time, 'sleep') as sleep:
            community_install._wait_for_steam_closed(messages.append)
        self.assertEqual(2, check.call_count)
        sleep.assert_called_once_with(2)
        self.assertEqual(1, len(messages))
        self.assertIn('Steam > Exit', messages[0])

    def test_wait_times_out_without_ignoring_running_processes(self):
        with patch.object(steam_install_options, '_steam_closed',
                          side_effect=steam_install_options.ProcessesRunning('running')), \
                patch.object(community_install.time, 'monotonic', side_effect=[0, 301]), \
                patch.object(community_install.time, 'sleep') as sleep:
            with self.assertRaisesRegex(ValueError, 'prepared files were preserved'):
                community_install._wait_for_steam_closed(lambda _: None)
        sleep.assert_not_called()

    def test_existing_matching_csp_and_missing_files_pass_read_only_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game, package = root / 'game', root / 'package'
            game.mkdir()
            package.mkdir()
            proxy = game / 'dwrite.dll'
            proxy.write_bytes(b'pinned')
            manifest = {'files': [{'path': 'dwrite.dll', 'sha256': hashlib.sha256(b'pinned').hexdigest()},
                                  {'path': 'extension/needed.lua', 'sha256': 'a' * 64}]}
            before = proxy.stat().st_mtime_ns
            with patch.object(community_install, '_verify_kit', return_value=manifest):
                community_install.preflight_csp(root, game, package)
            self.assertEqual(before, proxy.stat().st_mtime_ns)
            self.assertFalse((game / 'extension').exists())
            self.assertFalse((package / 'launcher').exists())

    def test_known_csp_upgrade_and_interrupted_upgrade_reach_the_existing_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game, package = root / 'game', root / 'package'
            game.mkdir()
            (package / 'launcher').mkdir(parents=True)
            receipt = package / 'launcher/csp.json'
            previous = dict(status='ready', version='0.3.0',
                            archive_sha256='2551975ad902deca0a4f3764a7ee154109a4c7e5198fef5ae499deaf77753747')
            manifest = dict(version=community_install.csp.VERSION,
                            archive_sha256=community_install.csp.ARCHIVE_SHA256, files=[])
            with patch.object(community_install, '_verify_kit', return_value=manifest):
                for record in (previous, dict(manifest, status='installing', previous=previous)):
                    with self.subTest(status=record['status']):
                        receipt.write_text(json.dumps(record))
                        community_install.preflight_csp(root, game, package)
                        self.assertEqual(record, json.loads(receipt.read_text()))
                receipt.write_text(json.dumps(dict(previous, archive_sha256='a' * 64)))
                with self.assertRaisesRegex(ValueError, 'explicit recovery'):
                    community_install.preflight_csp(root, game, package)

    def test_missing_game_explains_steam_installation_before_optional_manual_path(self):
        messages = []
        with patch.object(community_install.install_discovery, 'discover', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'Install Assetto Corsa from Steam'):
                community_install.choose_game(prompt=lambda _: '', output=messages.append)
        self.assertTrue(any('244210' in message for message in messages))


if __name__ == '__main__':
    unittest.main()
