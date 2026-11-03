"""Exercise CSP 0.3.0 migration with synthetic files and no simulator."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.launcher import csp


OLD_HASH = '2551975ad902deca0a4f3764a7ee154109a4c7e5198fef5ae499deaf77753747'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def rows(files):
    return [dict(path=name, sha256=digest(data), size_bytes=len(data))
            for name, data in files.items()]


class CSPCommunityMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.game, self.package, self.payload = root/'game', root/'package', root/'payload'
        for path in (self.game, self.package, self.payload):
            path.mkdir()
        exe = b'synthetic executable, never executed'
        put(self.game, 'acs.exe', exe)
        put(self.package, 'prepared.json', json.dumps(dict(
            status='prepared', content_scope='installed_content', game_mode='installed',
            source=str(self.game), selection=[dict(relative_path='acs.exe', sha256=digest(exe))],
        )).encode())
        self.old_files = {'dwrite.dll': b'old proxy', 'extension/config/old.ini': b'old',
                          'extension/config/shared.ini': b'old shared'}
        self.new_files = {'dwrite.dll': b'new proxy', 'extension/config/shared.ini': b'new shared',
                          'extension/config/new.ini': b'new'}
        for name, data in self.old_files.items():
            put(self.game, name, data)
        for name, data in self.new_files.items():
            put(self.payload, name, data)
        self.old = dict(schema_version=1, status='ready', version='0.3.0',
                        archive_sha256=OLD_HASH, installed_utc='2026-01-01T00:00:00+00:00',
                        files=rows(self.old_files))
        self.new = dict(schema_version=1, version=csp.VERSION,
                        archive_sha256=csp.ARCHIVE_SHA256, files=rows(self.new_files))
        put(self.package, 'launcher/csp.json', json.dumps(self.old).encode())
        put(self.payload, 'manifest.json', json.dumps(self.new).encode())
        # The small fixture has no third-party configuration. verify() still checks
        # every path, size and hash; only real CSP profile content is out of scope.
        self.profile_check = patch.object(csp, 'check_profiles')
        self.profile_check.start()
        self.addCleanup(self.profile_check.stop)

    def test_upgrade_and_restore_keep_unrelated_mod(self):
        put(self.game, 'extension/user-mod/keep.lua', b'player content')
        updated = csp.install(self.payload, self.package)
        self.assertEqual(('0.3.1', 'ready', OLD_HASH),
                         (updated['version'], updated['status'], updated['rollback']))
        self.assertFalse((self.game/'extension/config/old.ini').exists())
        for name, data in self.new_files.items():
            self.assertEqual(data, (self.game/name).read_bytes())
        self.assertEqual(self.old, csp.restore(self.package))
        for name, data in self.old_files.items():
            self.assertEqual(data, (self.game/name).read_bytes())
        self.assertFalse((self.game/'extension/config/new.ini').exists())
        self.assertEqual(b'player content', (self.game/'extension/user-mod/keep.lua').read_bytes())

    def test_matching_existing_csp_is_adopted_without_rewriting_files(self):
        (self.package/'launcher/csp.json').unlink()
        for name, data in self.new_files.items():
            put(self.game, name, data)
        put(self.game, 'extension/user-mod/settings.ini', b'player settings')
        before = {name: (self.game/name).stat().st_mtime_ns for name in self.new_files}
        with patch.object(csp.safe, 'copy_verified') as copy:
            ready = csp.install(self.payload, self.package)
            self.assertEqual(ready, csp.install(self.payload, self.package))
        copy.assert_not_called()
        self.assertEqual('ready', ready['status'])
        self.assertEqual(before, {name: (self.game/name).stat().st_mtime_ns for name in self.new_files})
        self.assertEqual(b'player settings', (self.game/'extension/user-mod/settings.ini').read_bytes())

    def test_partial_matching_installation_is_completed_without_replacing_proxy(self):
        (self.package/'launcher/csp.json').unlink()
        (self.game/'extension/config/shared.ini').unlink()
        put(self.game, 'dwrite.dll', self.new_files['dwrite.dll'])
        before = (self.game/'dwrite.dll').stat().st_mtime_ns
        self.assertEqual('ready', csp.install(self.payload, self.package)['status'])
        self.assertEqual(before, (self.game/'dwrite.dll').stat().st_mtime_ns)
        for name, data in self.new_files.items():
            self.assertEqual(data, (self.game/name).read_bytes())
        self.assertEqual(b'old', (self.game/'extension/config/old.ini').read_bytes())

    def test_foreign_conflict_blocks_adoption_before_writing_receipt(self):
        receipt = self.package/'launcher/csp.json'
        receipt.unlink()
        with patch.object(csp.safe, 'copy_verified') as copy:
            with self.assertRaisesRegex(ValueError, 'desconhecido'):
                csp.install(self.payload, self.package)
        copy.assert_not_called()
        self.assertFalse(receipt.exists())
        self.assertEqual(b'old proxy', (self.game/'dwrite.dll').read_bytes())

    def test_modified_previous_file_stops_before_mutation(self):
        put(self.game, 'extension/config/shared.ini', b'player edit')
        before = (self.package/'launcher/csp.json').read_bytes()
        with self.assertRaises(ValueError):
            csp.install(self.payload, self.package)
        self.assertEqual(before, (self.package/'launcher/csp.json').read_bytes())
        self.assertEqual(b'player edit', (self.game/'extension/config/shared.ini').read_bytes())
        self.assertEqual(b'old proxy', (self.game/'dwrite.dll').read_bytes())
        self.assertFalse((self.package/'launcher/csp-backups').exists())

    def test_unrecognized_previous_version_and_new_file_conflict_stop(self):
        receipt = self.package/'launcher/csp.json'
        invalid = dict(self.old, archive_sha256='a'*64)
        receipt.write_text(json.dumps(invalid), encoding='utf-8')
        with self.assertRaises(ValueError):
            csp.install(self.payload, self.package)
        self.assertEqual(invalid, json.loads(receipt.read_text(encoding='utf-8')))
        receipt.write_text(json.dumps(self.old), encoding='utf-8')
        put(self.game, 'extension/config/new.ini', b'unknown player file')
        with self.assertRaises(ValueError):
            csp.install(self.payload, self.package)
        self.assertEqual(b'unknown player file', (self.game/'extension/config/new.ini').read_bytes())
        self.assertEqual(self.old, json.loads(receipt.read_text(encoding='utf-8')))

    def test_interrupted_upgrade_can_resume_with_old_proxy_intact(self):
        real_copy = csp.safe.copy_verified

        def interrupt_proxy(source, destination, expected):
            if Path(source) == self.payload/'dwrite.dll':
                raise OSError('synthetic interruption before proxy copy')
            return real_copy(source, destination, expected)

        with patch.object(csp.safe, 'copy_verified', side_effect=interrupt_proxy):
            with self.assertRaises(OSError):
                csp.install(self.payload, self.package)
        self.assertEqual(b'old proxy', (self.game/'dwrite.dll').read_bytes())
        pending = json.loads((self.package/'launcher/csp.json').read_text(encoding='utf-8'))
        self.assertEqual('installing', pending['status'])
        self.assertEqual('ready', csp.install(self.payload, self.package)['status'])
        self.assertEqual(b'new proxy', (self.game/'dwrite.dll').read_bytes())
        self.assertEqual(self.old, csp.restore(self.package))

    def test_corrupt_backup_is_not_restored(self):
        csp.install(self.payload, self.package)
        backup = self.package/'launcher/csp-backups'/OLD_HASH/'dwrite.dll'
        backup.write_bytes(b'corrupt backup')
        receipt = self.package/'launcher/csp.json'
        before = receipt.read_bytes()
        with self.assertRaises(ValueError):
            csp.restore(self.package)
        self.assertEqual(before, receipt.read_bytes())
        self.assertEqual(b'new proxy', (self.game/'dwrite.dll').read_bytes())

    def test_interrupted_restore_can_resume(self):
        csp.install(self.payload, self.package)
        with patch.object(csp.safe, 'copy_verified', side_effect=OSError('synthetic interruption')):
            with self.assertRaises(OSError):
                csp.restore(self.package)
        self.assertEqual(b'new proxy', (self.game/'dwrite.dll').read_bytes())
        self.assertEqual(self.old, csp.restore(self.package))
        self.assertEqual(b'old proxy', (self.game/'dwrite.dll').read_bytes())


if __name__ == '__main__':
    unittest.main()
