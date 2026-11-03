"""Steam discovery against synthetic metadata and directories only."""
import os
from pathlib import Path
import tempfile
import unittest

from src.launcher import file_io, install_discovery as discovery


def quoted(value):
    return str(value).replace('\\', '\\\\').replace('"', '\\"')


class InstallDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir()
        self.steam = self.home / '.local/share/Steam'
        (self.steam / 'steamapps').mkdir(parents=True)

    def game(self, library, name='assettocorsa'):
        root = library / 'steamapps/common' / name
        for name in ('acs.exe', 'AssettoCorsa.exe', 'cfg/video.ini', 'cfg/controls.ini',
                     'system/cfg/inireaderdocuments.ini'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic fixture')
        (library / 'steamapps/appmanifest_244210.acf').write_text(
            '"AppState" { "appid" "244210" "installdir" "assettocorsa" }',
            encoding='utf-8')
        return root

    def libraries(self, value):
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(value, encoding='utf-8')

    def test_primary_and_additional_library_require_selection(self):
        first = self.game(self.steam)
        extra = self.home / 'library with spaces'
        (extra / 'steamapps').mkdir(parents=True)
        second = self.game(extra)
        self.libraries('"libraryfolders" { "0" { "path" "' + quoted(self.steam) +
                       '" "apps" { "244210" "1" } } "1" { "path" "' +
                       quoted(extra) + '" } }')
        self.assertEqual(discovery.discover(self.home), [first, second])
        with self.assertRaisesRegex(ValueError, 'Select'):
            discovery.select_game([first, second])
        self.assertEqual(discovery.select_game([first, second], second), second)

    def test_legacy_library_and_explicit_path_work_without_running_steam(self):
        extra = self.home / 'external'
        (extra / 'steamapps').mkdir(parents=True)
        game = self.game(extra)
        self.libraries('// synthetic\n"libraryfolders" { "1" "' + quoted(extra) + '" }')
        self.assertEqual(discovery.discover(self.home), [game])
        self.assertEqual(discovery.select_game([game]), game)
        self.assertEqual(discovery.select_game([], game), game)
        with self.assertRaisesRegex(ValueError, 'Select'):
            discovery.select_game([])

    def test_root_scoped_libraries_do_not_mix_other_steam_roots(self):
        primary = self.game(self.steam)
        other = self.home/'other-steam'
        (other/'steamapps').mkdir(parents=True)
        other_game = self.game(other)
        extra = self.home/'shared-library'
        (extra/'steamapps').mkdir(parents=True)
        shared_game = self.game(extra)
        self.libraries('"libraryfolders" { "1" { "path" "' + quoted(extra) + '" } }')
        self.assertEqual([primary, shared_game], discovery.discover_from_root(self.steam))
        self.assertEqual([other_game], discovery.discover_from_root(other))
        self.assertNotIn(shared_game, discovery.discover_from_root(other))

    def test_root_scoped_scan_rejects_invalid_library_declarations(self):
        self.game(self.steam)
        self.libraries('"libraryfolders" { "1" "../other" }')
        with self.assertRaises(ValueError):
            discovery.discover_from_root(self.steam)

    def test_duplicate_steam_roots_and_library_are_not_duplicate_candidates(self):
        game = self.game(self.steam)
        alias = self.home / '.steam/steam'
        alias.parent.mkdir()
        try:
            alias.symlink_to(self.steam, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Cannot create symlink fixture: {error}')
        self.libraries('"libraryfolders" { "0" { "path" "' + quoted(self.steam) + '" } }')
        self.assertEqual(discovery.discover(self.home), [game])

    def test_rejects_untrusted_metadata_traversal_and_duplicates(self):
        for content in ('"libraryfolders" { "0" "../elsewhere" }',
                        '"libraryfolders" { "0" "one" "0" "two" }',
                        '"libraryfolders" { "0" { "path" "broken" }',
                        '"libraryfolders" { "0" "bad\\q" }'):
            with self.subTest(content=content):
                self.libraries(content)
                with self.assertRaises(ValueError):
                    discovery.discover(self.home)

    def test_manifest_must_have_exact_id_and_one_component_install_name(self):
        self.game(self.steam)
        manifest = self.steam / 'steamapps/appmanifest_244210.acf'
        for appid, name in (('1', 'assettocorsa'), ('244210', '../other'),
                            ('244210', 'other/file')):
            with self.subTest(appid=appid, name=name):
                manifest.write_text('"AppState" { "appid" "' + appid +
                                    '" "installdir" "' + name + '" }', encoding='utf-8')
                with self.assertRaises((ValueError, file_io.SafetyError)):
                    discovery.discover(self.home)

    def test_manual_path_rejects_incomplete_and_hardlinked_files(self):
        game = self.game(self.steam)
        (game / 'cfg/video.ini').unlink()
        with self.assertRaises(ValueError):
            discovery.validate_game(game)
        (game / 'cfg/video.ini').write_bytes(b'synthetic')
        try:
            os.link(game / 'acs.exe', self.home / 'alias.exe')
        except OSError as error:
            self.skipTest(f'Cannot create hardlink fixture: {error}')
        with self.assertRaises(file_io.SafetyError):
            discovery.validate_game(game)

    def test_metadata_size_is_bounded(self):
        path = self.steam / 'steamapps/libraryfolders.vdf'
        path.write_bytes(b' ' * (discovery.MAX_VDF_BYTES + 1))
        with self.assertRaises(file_io.SafetyError):
            discovery.discover(self.home)


if __name__ == '__main__':
    unittest.main()
