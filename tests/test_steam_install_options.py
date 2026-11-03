"""Synthetic Steam configuration fixtures; never opens Steam or a game."""
from pathlib import Path
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.launcher import steam_install_options as options


def fixture(option=b''):
    return (b'// fixture\r\n"UserLocalConfigStore" { "Software" { "Valve" { '
            b'"Steam" { "apps" { "244210" { "Other" "preserve" ' + option +
            b' } "123" { "LaunchOptions" "other game" } } } } } }\r\n')


class SteamOptionsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base/'steam'
        self.target = self.root/'userdata'/'12345'/'config'/'localconfig.vdf'
        self.target.parent.mkdir(parents=True)
        self.receipt = self.base/'receipt.json'
        self.launcher = self.base/'ac-deck'
        self.launcher.write_text('fixture')
        self.package = self.base/'package'
        self.package.mkdir()
        self.closed = patch.object(options, '_steam_closed')
        self.closed.start()
        self.addCleanup(self.closed.stop)
        # Windows cannot fsync a directory; the production operation is Linux-only.
        if __import__('sys').platform != 'linux':
            sync = patch.object(options, '_sync_directory')
            sync.start()
            self.addCleanup(sync.stop)
            arg = patch.object(options, '_arg', side_effect=lambda p: '"'+Path(p).name+'"')
            arg.start()
            self.addCleanup(arg.stop)

    def install(self):
        return options.install(self.root, '12345', self.receipt, self.launcher, self.package,
                               steam_closed_confirmed=True)

    def restore(self):
        return options.restore(self.root, '12345', self.receipt, steam_closed_confirmed=True)

    def test_insert_and_restore_exact_bytes(self):
        before = fixture()
        self.target.write_bytes(before)
        result = self.install()
        self.assertTrue(result['inserted'])
        changed = self.target.read_bytes()
        self.assertIn(b'-- %command%', changed)
        self.assertIn(b'"other game"', changed)
        self.restore()
        self.assertEqual(before, self.target.read_bytes())

    def test_empty_existing_value_restores_exactly(self):
        before = fixture(b'"LaunchOptions" ""')
        self.target.write_bytes(before)
        self.assertFalse(self.install()['inserted'])
        self.restore()
        self.assertEqual(before, self.target.read_bytes())

    def test_restore_preserves_unrelated_change(self):
        self.target.write_bytes(fixture())
        self.install()
        self.target.write_bytes(self.target.read_bytes().replace(b'"preserve"', b'"new value"'))
        self.restore()
        self.assertEqual(fixture().replace(b'"preserve"', b'"new value"'), self.target.read_bytes())

    def test_user_launch_option_change_blocks_restore(self):
        self.target.write_bytes(fixture())
        self.install()
        changed = self.target.read_bytes().replace(b'-- %command%', b'-- changed')
        self.target.write_bytes(changed)
        with self.assertRaises(options.OptionsError):
            self.restore()
        self.assertEqual(changed, self.target.read_bytes())

    def test_existing_nonempty_options_never_overwritten(self):
        before = fixture(b'"LaunchOptions" "some command"')
        self.target.write_bytes(before)
        with self.assertRaises(options.OptionsError):
            self.install()
        self.assertEqual(before, self.target.read_bytes())
        self.assertFalse(self.receipt.exists())

    def test_literal_environment_options_are_preserved_and_restored_exactly(self):
        for value in ('WINEDLLOVERRIDES="dwrite=n,b;other=b" PROTON_NO_ESYNC=1 %command%',
                      "CUSTOM_VALUE='literal text; with spaces' EMPTY= %command%", '%command%'):
            with self.subTest(value=value):
                self.receipt.unlink(missing_ok=True)
                before = fixture(b'"LaunchOptions" ' + options._quote(value))
                self.target.write_bytes(before)
                first = self.install()
                command = options._locate(self.target.read_bytes())[2][3]
                self.assertTrue(command.endswith('-- %command%'))
                self.assertEqual(options._environment_prefix(value), command[:command.index('"ac-deck"')]
                                 if sys.platform != 'linux' else command[:command.index('"' + str(self.launcher) + '"')])
                self.assertEqual(first, self.install())
                self.restore()
                self.assertEqual(before, self.target.read_bytes())

    def test_shell_wrappers_expansions_and_extra_arguments_are_preserved(self):
        for value in ('wrapper %command%', 'A=$HOME %command%', 'A=`id` %command%',
                      'A=1; B=2 %command%', 'A=1 | %command%', 'A=~ %command%',
                      'A=1 %command% argument', 'A=1 %command% %command%',
                      '"A=1" %command%', 'A=1\n%command%', 'A=1 $(id) %command%'):
            with self.subTest(value=value):
                before = fixture(b'"LaunchOptions" ' + options._quote(value)) if '\n' not in value else None
                if before is None:
                    with self.assertRaises(options.OptionsError):
                        options._environment_prefix(value)
                    continue
                self.target.write_bytes(before)
                with self.assertRaises(options.OptionsError):
                    self.install()
                self.assertEqual(before, self.target.read_bytes())
                self.assertFalse(self.receipt.exists())

    def test_identical_existing_command_is_adopted_without_changing_steam(self):
        self.target.write_bytes(fixture())
        self.install()
        installed = self.target.read_bytes()
        self.receipt.unlink()
        with patch.object(options, '_replace') as replace:
            record = self.install()
            self.assertEqual(record, self.install())
            self.restore()
        replace.assert_not_called()
        self.assertTrue(record['adopted'])
        self.assertEqual(installed, self.target.read_bytes())

    @unittest.skipUnless(sys.platform == 'linux', 'POSIX shell environment')
    def test_environment_prefix_reaches_a_synthetic_child_as_literal_values(self):
        value = "AC_DECK_TEST_TEXT='literal text; with spaces' AC_DECK_TEST_EMPTY= %command%"
        helper = 'import json,os;print(json.dumps([os.environ["AC_DECK_TEST_TEXT"],os.environ["AC_DECK_TEST_EMPTY"]]))'
        command = options._environment_prefix(value) + shlex.quote(sys.executable) + ' -c ' + shlex.quote(helper)
        child = subprocess.run(['/bin/sh', '-c', command], check=True, capture_output=True, text=True)
        self.assertEqual(['literal text; with spaces', ''], json.loads(child.stdout))

    def test_unique_most_recent_login_requires_an_existing_account_config(self):
        login = self.root/'config/loginusers.vdf'
        login.parent.mkdir()
        login.write_text('"users" { "76561197960278073" { "MostRecent" "1" } '
                         '"76561197960265770" { "MostRecent" "0" } }')
        self.assertEqual('12345', options.preferred_account(self.root, ['42', '12345']))
        self.assertIsNone(options.preferred_account(self.root, ['42']))
        login.write_text(login.read_text().replace('"MostRecent" "0"', '"MostRecent" "1"'))
        self.assertIsNone(options.preferred_account(self.root, ['42', '12345']))

    def test_missing_duplicate_malformed_paths_are_rejected(self):
        for bad in (fixture().replace(b'"apps"', b'"not-apps"'),
                    fixture().replace(b'"244210" {', b'"244210" {} "244210" {'),
                    fixture(b'"LaunchOptions" "" "LaunchOptions" ""'),
                    fixture()[:-4], b'\x00binary'):
            with self.subTest(data=bad), self.assertRaises((options.OptionsError, UnicodeError)):
                options._locate(bad)

    def test_receipt_cannot_be_overwritten(self):
        before = fixture()
        self.target.write_bytes(before)
        self.receipt.write_bytes(b'existing receipt')
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(before, self.target.read_bytes())
        self.assertEqual(b'existing receipt', self.receipt.read_bytes())

    def test_change_before_replace_is_preserved_and_receipt_kept(self):
        before = fixture()
        self.target.write_bytes(before)
        edited = before.replace(b'"preserve"', b'"human edit"')
        calls = 0
        def check():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.target.write_bytes(edited)
        with patch.object(options, '_steam_closed', side_effect=check):
            with self.assertRaises(options.OptionsError):
                self.install()
        self.assertEqual(edited, self.target.read_bytes())
        self.assertTrue(self.receipt.exists())

    def test_explicit_confirmation_and_account_selection(self):
        self.target.write_bytes(fixture())
        self.assertEqual(['12345'], options.discover_accounts(self.root))
        with self.assertRaises(options.OptionsError):
            options.install(self.root, '12345', self.receipt, self.launcher, self.package)
        for account in ('', '../12345', '0', '4294967296'):
            with self.subTest(account=account), self.assertRaises(options.OptionsError):
                options._target(self.root, account)

    def test_explicit_csp_payload_is_included_and_restored(self):
        before = fixture()
        self.target.write_bytes(before)
        payload = self.base/'csp'
        payload.mkdir()
        (payload/'manifest.json').write_text('{}')
        options.install(self.root, '12345', self.receipt, self.launcher, self.package,
                        csp_payload=payload, steam_closed_confirmed=True)
        self.assertIn(b'--kit-csp', self.target.read_bytes())
        self.restore()
        self.assertEqual(before, self.target.read_bytes())

    def test_different_account_cannot_restore_receipt(self):
        self.target.write_bytes(fixture())
        self.install()
        other = self.root/'userdata'/'42'/'config'/'localconfig.vdf'
        other.parent.mkdir(parents=True)
        other.write_bytes(fixture())
        with self.assertRaises(options.OptionsError):
            options.restore(self.root, '42', self.receipt, steam_closed_confirmed=True)
        self.assertEqual(fixture(), other.read_bytes())

    def test_missing_app_is_added_and_restored_exactly(self):
        before = fixture().replace(b'"244210" { "Other" "preserve"  } ', b'')
        self.target.write_bytes(before)
        result = self.install()
        self.assertTrue(result['inserted_app'])
        self.restore()
        self.assertEqual(before, self.target.read_bytes())

    def test_changed_inserted_app_is_not_removed(self):
        before = fixture().replace(b'"244210" { "Other" "preserve"  } ', b'')
        self.target.write_bytes(before)
        self.install()
        changed = self.target.read_bytes().replace(b'\t}\n', b'\t"NewSetting" "keep"\n\t}\n', 1)
        self.target.write_bytes(changed)
        with self.assertRaises(options.OptionsError):
            self.restore()
        with self.assertRaises(options.OptionsError):
            self.install()
        self.assertEqual(changed, self.target.read_bytes())

    def test_repeat_and_interrupted_install_can_resume(self):
        before = fixture()
        self.target.write_bytes(before)
        with patch.object(options, '_replace', side_effect=options.OptionsError('interrupted')):
            with self.assertRaises(options.OptionsError):
                self.install()
        self.assertEqual(before, self.target.read_bytes())
        self.restore()  # Already original; receipt stays for a retry.
        self.assertTrue(self.receipt.exists())
        first = self.install()
        installed = self.target.read_bytes()
        self.assertEqual(first, self.install())
        self.assertEqual(installed, self.target.read_bytes())
        self.restore()
        self.assertEqual(before, self.target.read_bytes())
        self.restore()

    @unittest.skipUnless(sys.platform == 'linux', 'Linux process fixtures')
    def test_process_check_allows_own_bootloader_but_rejects_other_instances(self):
        proc = self.base/'proc'
        for pid, parent, name in ((10, 9, 'ac-deck'), (9, 1, 'ac-deck'), (1, 0, 'init')):
            folder = proc/str(pid)
            folder.mkdir(parents=True)
            (folder/'status').write_text(f'Name:\t{name}\nPPid:\t{parent}\n')
            (folder/'comm').write_text(name+'\n')
        self.closed.stop()
        with patch.object(options, 'Path', side_effect=lambda value: proc if value == '/proc' else Path(value)), \
             patch.object(options.os, 'getpid', return_value=10):
            options._steam_closed()
            extra = proc/'20'
            extra.mkdir()
            (extra/'comm').write_text('ac-deck\n')
            with self.assertRaises(options.OptionsError):
                options._steam_closed()
            (extra/'comm').write_text('steam\n')
            with self.assertRaises(options.OptionsError):
                options._steam_closed()
        self.closed.start()

    @unittest.skipUnless(sys.platform == 'linux', 'Linux command paths')
    def test_command_paths_with_spaces_and_unsafe_shell_characters(self):
        self.assertEqual('"/tmp/Own Kit/ac-deck"', options._arg('/tmp/Own Kit/ac-deck'))
        for value in ('relative/path', '/tmp/$HOME', '/tmp/`command`', '/tmp/a"b', '/tmp/a\\b',
                      '/tmp/%command%/ac-deck', '/tmp/%COMMAND%/ac-deck'):
            with self.subTest(value=value), self.assertRaises(options.OptionsError):
                options._arg(value)
