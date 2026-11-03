"""Update/rollback synthetic community archives, without Steam or real player data."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import install_ac_deck as bootstrap, update_ac_deck as updater
from scripts.ciclo_entrega_lib.common import atomic_json, digest, file_state, locked, read_json


@unittest.skipUnless(sys.platform == 'linux', 'Community updates require Linux POSIX modes')
class CommunityUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.closed = patch.object(updater.steam_install_options, '_steam_closed')
        self.closed.start()
        self.addCleanup(self.closed.stop)
        self.old, self.old_sha = self.archive('old', {'_internal/obsolete.dat': b'obsolete'})
        self.new, self.new_sha = self.archive('new', {'_internal/new.dat': b'new'})
        self.destination = self.install('installation with spaces')

    def archive(self, version, extra=None, *, runtime='1', python='3.13.5', executable_mode=0o755):
        info = dict(schema_version=1, distribution='community', architecture='x86_64',
                    public_name='ac-deck', python=python, source_sha256={
                        'src/launcher/application.py':runtime*64,
                        'src/launcher/community_install.py':'2'*64,
                        'scripts/jogo_deck.py':'3'*64,
                        'scripts/build_launcher_linux.py':hashlib.sha256(version.encode()).hexdigest()})
        files = {'ac-deck': ('executable '+version).encode(), '_internal/runtime.dat':version.encode(),
                 'build-info.json':json.dumps(info).encode(), 'LICENSE':b'owned synthetic license',
                 'NOTICE':version.encode(), 'THIRD_PARTY_NOTICES.md':b'owned synthetic notices', **(extra or {})}
        files['manifest.json'] = json.dumps(dict(files=[dict(path=name, size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(files.items())])).encode()
        archive = self.root/(version+'.tar.gz')
        with tarfile.open(archive, 'w:gz') as tar:
            for name, data in files.items():
                row = tarfile.TarInfo(bootstrap.ROOT_NAME+'/'+name)
                row.size, row.mode = len(data), executable_mode if name == 'ac-deck' else 0o644
                tar.addfile(row, io.BytesIO(data))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def install(self, name):
        destination = self.root/name
        bootstrap.install(archive=self.old, sha256=self.old_sha, destination=destination)
        for relative, data in (('local/work/community/launcher/history.json',b'progress 1'),
                ('local/private/credentials.json',b'synthetic private data'),
                ('csp/dwrite.dll',b'synthetic CSP'), ('user.txt',b'unknown user file')):
            path = destination/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return destination

    def update(self, destination=None, **options):
        return updater.update(archive=self.new, sha256=self.new_sha,
            current_archive=self.old, current_sha256=self.old_sha,
            destination=destination or self.destination, confirmed=True, **options)

    def managed_files(self, destination=None):
        return updater.release(destination or self.destination, strict=False)['files']

    def test_update_preserves_unknown_player_csp_and_steam_options_data(self):
        unknown = self.destination/'_internal/user-plugin.dat'
        unknown.write_bytes(b'unknown plugin')
        self.update()
        self.assertEqual(b'executable new', (self.destination/'ac-deck').read_bytes())
        self.assertFalse((self.destination/'_internal/obsolete.dat').exists())
        self.assertEqual(b'unknown plugin', unknown.read_bytes())
        for name,data in (('csp/dwrite.dll',b'synthetic CSP'), ('user.txt',b'unknown user file'),
                          ('local/private/credentials.json',b'synthetic private data')):
            self.assertEqual(data, (self.destination/name).read_bytes())
        self.assertEqual('complete', updater.recover(destination=self.destination, confirmed=True)['status'])

    def test_first_adoption_requires_old_archive_anchor(self):
        with self.assertRaisesRegex(ValueError, 'First adoption'):
            updater.update(archive=self.new, sha256=self.new_sha, destination=self.destination, confirmed=True)
        self.assertEqual(b'executable old', (self.destination/'ac-deck').read_bytes())

    def test_subsequent_update_uses_owned_backup_and_rolls_back_only_last_runtime(self):
        self.update()
        archive, sha = self.archive('third', {'_internal/third.dat':b'third'})
        updater.update(archive=archive, sha256=sha, destination=self.destination, confirmed=True)
        progress = self.destination/'local/work/community/launcher/history.json'
        progress.write_bytes(b'progress after third package')
        self.assertEqual(b'executable third', (self.destination/'ac-deck').read_bytes())
        updater.recover(destination=self.destination, rollback=True, confirmed=True)
        self.assertEqual(b'executable new', (self.destination/'ac-deck').read_bytes())
        self.assertEqual(b'progress after third package', progress.read_bytes())
        self.assertEqual(2, len(list((self.destination/'local/distribution-update/transactions').iterdir())))

    def test_closed_acknowledgement_is_required_before_creating_update_storage(self):
        with self.assertRaisesRegex(ValueError, 'then pass --closed'):
            updater.update(archive=self.new, sha256=self.new_sha, destination=self.destination)
        self.assertFalse((self.destination/'local/distribution-update').exists())

    def test_unknown_collision_managed_edit_mode_edit_and_links_are_preserved(self):
        cases = ('collision', 'edit', 'mode', 'link')
        for case in cases:
            with self.subTest(case=case):
                destination = self.install(case)
                path = destination/('_internal/new.dat' if case == 'collision' else 'ac-deck')
                if case in ('collision', 'edit'):
                    path.write_bytes(b'user edit')
                elif case == 'mode':
                    path.chmod(0o644)
                else:
                    path.unlink()
                    path.symlink_to(destination/'user.txt')
                before = path.lstat()
                with self.assertRaises((ValueError, RuntimeError)):
                    self.update(destination)
                self.assertEqual(before.st_ino, path.lstat().st_ino)
                self.assertFalse((destination/'local/distribution-update/active.json').exists())

    def test_archive_hash_and_source_executable_mode_tamper_are_rejected(self):
        self.new.write_bytes(self.new.read_bytes()+b'changed')
        with self.assertRaisesRegex(bootstrap.InstallError, 'SHA-256'):
            self.update()
        bad, sha = self.archive('bad-mode', executable_mode=0o644)
        with self.assertRaisesRegex(ValueError, 'Unsupported older preview'):
            updater.update(archive=bad, sha256=sha, current_archive=self.old,
                current_sha256=self.old_sha, destination=self.destination, confirmed=True)
        self.assertEqual(b'executable old', (self.destination/'ac-deck').read_bytes())

    def test_player_roots_cannot_be_claimed_by_an_archive_manifest(self):
        for name in ('local/progress.json', 'csp/dwrite.dll'):
            archive, sha = self.archive('forbidden-'+name.split('/')[0], {name:b'must not replace data'})
            with self.assertRaisesRegex(ValueError, 'Unsupported managed'):
                updater.update(archive=archive, sha256=sha, current_archive=self.old,
                    current_sha256=self.old_sha, destination=self.destination, confirmed=True)
        self.assertEqual(b'progress 1', (self.destination/'local/work/community/launcher/history.json').read_bytes())
        self.assertEqual(b'synthetic CSP', (self.destination/'csp/dwrite.dll').read_bytes())

    def test_frozen_source_mode_change_blocks_before_runtime_replacement(self):
        save = updater.atomic_json
        def changed(path, value):
            save(path, value)
            if path.name == 'active.json' and not value['complete']:
                source = path.parent/'transactions'/value['id']/'after'/bootstrap.ROOT_NAME/'NOTICE'
                source.chmod(0o755)
        with patch.object(updater, 'atomic_json', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Frozen update input'):
                self.update()
        self.assertEqual(b'executable old', (self.destination/'ac-deck').read_bytes())
        self.assertFalse((self.destination/'local/distribution-update/installed.json').exists())

    def test_malformed_manifest_and_source_identity_fail_with_boundary_errors(self):
        stage = self.root/'schema-stage'
        stage.mkdir()
        bootstrap._extract_archive(self.new, stage)
        source = stage/bootstrap.ROOT_NAME
        manifest = source/'manifest.json'
        original = manifest.read_bytes()
        manifest.write_text('{"files":{}}')
        with self.assertRaisesRegex(ValueError, 'files array'):
            updater.release(source, strict=True)
        manifest.write_bytes(original)
        info = json.loads((source/'build-info.json').read_bytes())
        info['source_sha256']['src/launcher/application.py'] = 123
        raw = json.dumps(info).encode()
        (source/'build-info.json').write_bytes(raw)
        document = json.loads(original)
        row = next(row for row in document['files'] if row['path'] == 'build-info.json')
        row.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        manifest.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, 'source identity'):
            updater.release(source, strict=True)

    def test_resume_after_replacement_deletion_and_manifest_response_loss(self):
        for point in ('copy1', 'copy2', 'delete', 'manifest'):
            with self.subTest(point=point):
                destination = self.install('recovery-'+point)
                original_replace, original_unlink = Path.replace, Path.unlink
                copied = 0
                def replace(path, target):
                    nonlocal copied
                    result = original_replace(path, target)
                    if path.name.startswith('.ac-deck-update-'):
                        if Path(target) == destination/'manifest.json' and point == 'manifest':
                            raise OSError('lost manifest response')
                        copied += 1
                        if point == 'copy'+str(copied):
                            raise OSError('lost replacement response')
                    return result
                def unlink(path, *args, **kwargs):
                    result = original_unlink(path, *args, **kwargs)
                    if path == destination/'_internal/obsolete.dat' and point == 'delete':
                        raise OSError('lost deletion response')
                    return result
                with patch.object(Path, 'replace', replace), patch.object(Path, 'unlink', unlink):
                    with self.assertRaises(OSError):
                        self.update(destination)
                updater.recover(destination=destination, confirmed=True)
                self.assertEqual(b'executable new', (destination/'ac-deck').read_bytes())
                self.assertFalse((destination/'_internal/obsolete.dat').exists())
                self.assertTrue(read_json(destination/'local/distribution-update/active.json')['complete'])

    def test_lost_ownership_or_final_receipt_reconciles_without_runtime_replacement(self):
        for point in ('installed.json', 'active.json'):
            with self.subTest(point=point):
                destination = self.install('lost-'+point)
                save = updater.atomic_json
                def lost(path, value):
                    save(path, value)
                    if path.name == point and (point == 'installed.json' or value.get('complete')):
                        raise OSError('lost receipt response')
                with patch.object(updater, 'atomic_json', side_effect=lost):
                    with self.assertRaises(OSError):
                        self.update(destination)
                with patch.object(updater, 'copy', side_effect=AssertionError('runtime must already match')):
                    updater.recover(destination=destination, confirmed=True)

    def test_missing_final_owned_receipt_is_reconstructed_but_changed_receipt_is_preserved(self):
        self.update()
        marker = self.destination/'local/distribution-update/installed.json'
        expected = marker.read_bytes()
        marker.unlink()
        with patch.object(updater, 'copy', side_effect=AssertionError('runtime must not be replaced')):
            updater.recover(destination=self.destination, confirmed=True)
        self.assertEqual(expected, marker.read_bytes())
        marker.write_text('{"user":"changed receipt"}')
        with self.assertRaisesRegex(ValueError, 'receipt changed'):
            updater.recover(destination=self.destination, confirmed=True)
        self.assertEqual('{"user":"changed receipt"}', marker.read_text())

    def test_concurrent_update_lock_and_unknown_journal_storage_refuse_before_runtime_changes(self):
        target, home = updater.storage(self.destination)
        updater.own_storage(target, home)
        with locked(home/'update.lock'):
            with self.assertRaisesRegex(RuntimeError, 'execução'):
                self.update()
        other = self.install('unknown journal')
        journal = other/'local/distribution-update'
        journal.mkdir(parents=True)
        (journal/'user-file').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'Unknown update storage'):
            self.update(other)
        self.assertEqual(b'unknown', (journal/'user-file').read_bytes())
        self.assertEqual(b'executable old', (other/'ac-deck').read_bytes())

    def test_unselected_symlink_is_preserved_without_following_it(self):
        outside = self.root/'outside'
        outside.mkdir()
        (outside/'player-data').write_bytes(b'preserved')
        link = self.destination/'unknown-link'
        link.symlink_to(outside, target_is_directory=True)
        self.update()
        self.assertTrue(link.is_symlink())
        self.assertEqual(b'preserved', (outside/'player-data').read_bytes())

    def test_partial_copy_and_concurrent_target_edit_are_preserved(self):
        copy = updater.copy
        def interrupted(source, target, wanted):
            if target.name.startswith('.ac-deck-update-'):
                target.write_bytes(b'partial copy')
                raise OSError('partial copy')
            return copy(source, target, wanted)
        with patch.object(updater, 'copy', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'partial'):
                self.update()
        partial = list(self.destination.glob('**/.ac-deck-update-*.new'))
        self.assertTrue(partial)
        victim = self.destination/'ac-deck'
        victim.write_bytes(b'new user edit')
        with self.assertRaisesRegex(ValueError, 'diverges'):
            updater.recover(destination=self.destination, confirmed=True)
        self.assertEqual(b'new user edit', victim.read_bytes())
        self.assertEqual(b'partial copy', partial[0].read_bytes())

    def test_concurrent_edit_during_copy_is_not_replaced(self):
        copy = updater.copy
        victims = []
        def changed(source, target, wanted):
            result = copy(source, target, wanted)
            if target.name.startswith('.ac-deck-update-'):
                victim = target.parent/source.name
                victims.append(victim)
                victim.write_bytes(b'concurrent edit')
            return result
        with patch.object(updater, 'copy', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'changed during copy'):
                self.update()
        self.assertEqual(b'concurrent edit', victims[0].read_bytes())

    def test_temporary_replaced_by_link_cannot_change_unknown_file_modes(self):
        source = self.destination/'NOTICE'
        external = self.root/'unknown-private-file'
        external.write_bytes(b'unknown data')
        external.chmod(0o600)
        temporary = self.root/'temporary-copy'
        copy = updater.safe.copy_verified
        def replace(source, destination, sha):
            copy(source, destination, sha)
            destination.unlink()
            destination.symlink_to(external)
        with patch.object(updater.safe, 'copy_verified', side_effect=replace):
            with self.assertRaises(RuntimeError):
                updater.copy(source, temporary, file_state(source))
        self.assertEqual(0o600, external.stat().st_mode & 0o777)
        self.assertEqual(b'unknown data', external.read_bytes())

    def test_regular_temporary_replacement_preserves_foreign_bytes_and_mode(self):
        source = self.destination/'NOTICE'
        temporary = self.root/'temporary-copy'
        copy = updater.safe.copy_verified
        def replace(source, destination, sha):
            copy(source, destination, sha)
            destination.unlink()
            destination.write_bytes(b'foreign replacement')
            destination.chmod(0o600)
        with patch.object(updater.safe, 'copy_verified', side_effect=replace):
            with self.assertRaisesRegex(ValueError, 'changed before mode'):
                updater.copy(source, temporary, file_state(source))
        self.assertEqual(0o600, temporary.stat().st_mode & 0o777)
        self.assertEqual(b'foreign replacement', temporary.read_bytes())

    def test_regular_replacement_between_hash_and_fd_open_is_detected_by_identity(self):
        source = self.destination/'NOTICE'
        wanted = file_state(source)
        temporary = self.root/'temporary-copy'
        copied = False
        copy, hashed = updater.safe.copy_verified, updater.safe.hash_reference_file
        def after_copy(source, destination, sha):
            nonlocal copied
            result = copy(source, destination, sha)
            copied = True
            return result
        def after_hash(path):
            result = hashed(path)
            if copied and path == temporary:
                path.unlink()
                path.write_bytes(source.read_bytes())
                path.chmod(0o600)
            return result
        with patch.object(updater.safe, 'copy_verified', side_effect=after_copy), \
                patch.object(updater.safe, 'hash_reference_file', side_effect=after_hash):
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                updater.copy(source, temporary, wanted)
        self.assertEqual(0o600, temporary.stat().st_mode & 0o777)
        self.assertEqual(source.read_bytes(), temporary.read_bytes())

    def test_rollback_keeps_newer_progress_and_can_resume_after_interruption(self):
        old = self.managed_files()
        self.update()
        progress = self.destination/'local/work/community/launcher/history.json'
        progress.write_bytes(b'newer progress 2')
        original = Path.replace
        def lost(path, target):
            result = original(path, target)
            if path.name.startswith('.ac-deck-update-'):
                raise OSError('rollback interrupted')
            return result
        with patch.object(Path, 'replace', lost):
            with self.assertRaisesRegex(OSError, 'rollback interrupted'):
                updater.recover(destination=self.destination, rollback=True, confirmed=True)
        updater.recover(destination=self.destination, confirmed=True)
        self.assertEqual(old, self.managed_files())
        self.assertEqual(b'newer progress 2', progress.read_bytes())
        self.assertEqual(b'synthetic CSP', (self.destination/'csp/dwrite.dll').read_bytes())

    def test_different_runtime_or_python_data_identity_refuses_update(self):
        before = self.managed_files()
        for name, options in (('different-runtime',dict(runtime='4')), ('different-python',dict(python='3.14.0'))):
            archive, sha = self.archive(name, **options)
            with self.assertRaisesRegex(ValueError, 'migration contract'):
                updater.update(archive=archive, sha256=sha, current_archive=self.old,
                    current_sha256=self.old_sha, destination=self.destination, confirmed=True)
            self.assertEqual(before, self.managed_files())

    def test_incompatible_rollback_journal_is_refused_without_reverting_data(self):
        archive, sha = self.archive('incompatible-current', runtime='4')
        destination = self.root/'incompatible installation'
        bootstrap.install(archive=archive, sha256=sha, destination=destination)
        progress = destination/'local/progress.json'
        progress.parent.mkdir()
        progress.write_bytes(b'new incompatible schema data')
        target, home = updater.storage(destination)
        updater.own_storage(target, home)
        token = 'a'*32
        transaction = home/'transactions'/token
        transaction.mkdir(parents=True)
        _, old = updater.stage(self.old, self.old_sha, transaction/'before')
        _, new = updater.stage(archive, sha, transaction/'after')
        old['archive_sha256'], new['archive_sha256'] = self.old_sha, sha
        plan = dict(schema=1, id=token, target=str(target), old=old, new=new, previous_receipt=None)
        atomic_json(transaction/'plan.json', plan)
        atomic_json(home/'active.json', dict(schema=1,id=token,target=str(target),direction='update',
                                            complete=True,plan_sha256=digest(plan)))
        with self.assertRaisesRegex(ValueError, 'migration contract'):
            updater.recover(destination=destination, rollback=True, confirmed=True)
        self.assertEqual(b'new incompatible schema data', progress.read_bytes())
        self.assertEqual(b'executable incompatible-current', (destination/'ac-deck').read_bytes())

    def test_completed_runtime_edits_and_backup_edits_are_not_silently_repaired(self):
        self.update()
        (self.destination/'ac-deck').write_bytes(b'executable old')
        with self.assertRaisesRegex(ValueError, 'Completed distribution'):
            updater.recover(destination=self.destination, confirmed=True)
        state = read_json(self.destination/'local/distribution-update/active.json')
        backup = self.destination/'local/distribution-update/transactions'/state['id']/'before'/bootstrap.ROOT_NAME/'NOTICE'
        backup.write_bytes(b'changed backup')
        with self.assertRaisesRegex(ValueError, 'changed'):
            updater.recover(destination=self.destination, rollback=True, confirmed=True)

    def test_saved_archive_identity_remains_required_on_resume(self):
        self.update()
        home = self.destination/'local/distribution-update'
        state = read_json(home/'active.json')
        saved = home/'transactions'/state['id']/'after/archive.tar.gz'
        saved.unlink()
        with self.assertRaisesRegex(ValueError, 'archive changed or is missing'):
            updater.recover(destination=self.destination, confirmed=True)
        self.assertEqual(b'executable new', (self.destination/'ac-deck').read_bytes())


if __name__ == '__main__':
    unittest.main()
