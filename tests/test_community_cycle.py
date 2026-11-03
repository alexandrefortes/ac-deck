"""Community recovery boundaries use independent files and no compiler or game."""
import copy
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import exportar_ac_deck as exporter
from scripts.ciclo_entrega_lib import community, community_verify
from scripts.ciclo_entrega_lib.common import CycleError, atomic_json, file_state, read_json


class CommunityCycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.folder = self.root/'local/work/ciclos/fixture'
        self.folder.mkdir(parents=True)
        self.source = self.root/'fixture.py'
        self.source.write_text('value = 1\n')
        self.rows = {'fixture.py':dict(source_path='fixture.py', **exporter.fingerprint(self.source))}
        self.inputs = dict(source_tree='working-tree', source_base=None, files=self.rows)
        self.plan = dict(id='fixture', inputs=self.inputs, steps=['preflight', 'snapshot'])
        self.state = dict(steps={})
        self.local = dict(community=dict(work=str(self.root/'build work')))
        self.runner = community.Runner(self.root, self.folder, self.state, {}, self.local)

    def run_cycle(self, until=None):
        with patch.object(community, 'inputs', return_value=copy.deepcopy(self.inputs)):
            return self.runner.execute(self.plan, until=until)

    def test_resume_reuses_only_exact_source_and_environment(self):
        self.run_cycle()
        snapshot = Path(self.state['steps']['snapshot']['result']['tree'])
        self.assertEqual(self.source.read_bytes(), (snapshot/'fixture.py').read_bytes())
        with patch.object(self.runner, 'perform', side_effect=AssertionError('must reuse')):
            self.run_cycle()
        changed = copy.deepcopy(self.inputs)
        changed['environment'] = {'dependency': 'changed'}
        with patch.object(community, 'inputs', return_value=changed):
            with self.assertRaisesRegex(CycleError, 'divergem do plano'):
                self.runner.execute(self.plan)
        (snapshot/'fixture.py').write_text('foreign\n')
        with self.assertRaisesRegex(CycleError, 'Snapshot mudou'):
            self.run_cycle()
        self.assertEqual('foreign\n', (snapshot/'fixture.py').read_text())

    def test_interruption_preserves_receipt_and_creates_new_attempt(self):
        original = self.runner.perform
        def failed(step, plan, attempt):
            if step == 'snapshot':
                (attempt/'partial-output').write_text('keep\n')
                raise OSError('injected interruption')
            return original(step, plan, attempt)
        with patch.object(self.runner, 'perform', side_effect=failed):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.run_cycle()
        failed_attempt = Path(self.state['steps']['snapshot']['attempt'])
        self.assertEqual('failed', read_json(failed_attempt/'receipt.json')['status'])
        self.run_cycle()
        self.assertEqual('keep\n', (failed_attempt/'partial-output').read_text())
        self.assertNotEqual(str(failed_attempt), self.state['steps']['snapshot']['attempt'])

    def test_snapshot_accepts_owned_build_output_but_refuses_source_extras(self):
        self.run_cycle()
        tree = Path(self.state['steps']['snapshot']['result']['tree'])
        generated = tree/'local/work/community-123/build/generated'
        generated.parent.mkdir(parents=True)
        generated.write_text('compiled fixture\n')
        self.run_cycle()
        (tree/'unreviewed.py').write_text('value=2\n')
        with self.assertRaisesRegex(CycleError, 'extras'):
            self.run_cycle()

    def test_json_roundtrip_is_unchanged(self):
        self.inputs['environment'] = dict(libc=['glibc', '2.39'])
        atomic_json(self.folder/'plan.json', self.plan)
        self.plan = read_json(self.folder/'plan.json')
        self.run_cycle()

    def test_candidate_refuses_promotion_before_any_operation(self):
        self.plan['steps'] = ['apply']
        with patch.object(community, 'inputs', side_effect=AssertionError('must refuse first')):
            with self.assertRaisesRegex(CycleError, 'promoção'):
                self.runner.execute(self.plan)

    def test_sdk_inventory_is_explicit_exclusive_and_rejects_external_links(self):
        sdk = self.root/'sdk'
        sdk.mkdir()
        (sdk/'python').write_bytes(b'owned fixture')
        self.local['sdk'] = dict(python_root=str(sdk))
        output = self.root/'sdk-manifest.json'
        report = community.sdk_inventory(self.root, self.local, output)
        self.assertEqual(1, report['entries'])
        before = output.read_bytes()
        with self.assertRaisesRegex(CycleError, 'já existe'):
            community.sdk_inventory(self.root, self.local, output)
        self.assertEqual(before, output.read_bytes())
        if os.name != 'nt':
            (sdk/'outside').symlink_to(self.source)
            with self.assertRaisesRegex(CycleError, 'fora'):
                community.python_inventory(sdk)

    def test_work_overlap_is_rejected_before_reading_or_writing_sdk(self):
        sdk = self.root/'sdk'
        sdk.mkdir()
        config = dict(python=['configured-python'], python_root=str(sdk/'python'),
                      python_manifest=str(sdk/'manifest.json'), native=str(sdk/'native/lib'),
                      font=str(sdk/'native/font.ttf'), licenses=str(sdk/'notices'))
        for path in (sdk, sdk/'python/work', sdk/'native/lib/work', sdk/'notices/work',
                     sdk/'native/font.ttf', sdk/'manifest.json'):
            with self.subTest(work=path):
                local = dict(sdk=config, community=dict(work=str(path)))
                with self.assertRaisesRegex(CycleError, 'separado'):
                    community.inputs(self.root, {}, local)
                self.assertEqual([], list(sdk.iterdir()))
        occupied = self.root/'work-file'
        occupied.write_bytes(b'preserved')
        with self.assertRaisesRegex(CycleError, 'arquivo preservado'):
            community.inputs(self.root, {}, dict(sdk=config, community=dict(work=str(occupied))))
        self.assertEqual(b'preserved', occupied.read_bytes())

    def test_work_mode_probe_refuses_unsupported_filesystem_without_residue(self):
        work = self.root/'mode work'
        work.mkdir()
        sentinel = work/'preserved.txt'
        sentinel.write_bytes(b'preserved')
        with patch.object(community.os, 'fchmod', return_value=None, create=True):
            with self.assertRaisesRegex(CycleError, 'filesystem Linux'):
                community.check_work_modes(work)
        self.assertEqual([sentinel], list(work.iterdir()))
        self.assertEqual(b'preserved', sentinel.read_bytes())
        if hasattr(os, 'fchmod'):
            community.check_work_modes(work)
            self.assertEqual([sentinel], list(work.iterdir()))

    def test_package_and_verify_runtime_destinations_use_configured_work(self):
        self.run_cycle()
        self.local['sdk'] = {}
        self.state['steps']['build'] = dict(status='done', result=dict(bundle='bundle', archive='archive'))
        package_attempt = self.folder/'attempts/package-fixture'
        with patch.object(community_verify, 'verify_archive') as package:
            result = self.runner.perform('package', self.plan, package_attempt)
        work = Path(self.local['community']['work'])/'fixture'
        relocated = Path(result['relocated'])
        self.assertTrue(relocated.is_relative_to(work))
        self.assertFalse(relocated.is_relative_to(self.folder))
        self.assertEqual(relocated, package.call_args.args[2])
        self.state['steps']['package'] = dict(status='done', result=result)
        verify_attempt = self.folder/'attempts/verify-fixture'
        with patch.object(community_verify, 'verify') as verify:
            verified = self.runner.perform('verify', self.plan, verify_attempt)
        runtime = verify.call_args.args[3]
        self.assertTrue(runtime.is_relative_to(work))
        self.assertFalse(runtime.is_relative_to(self.folder))
        self.assertEqual(str(runtime/'evidence'), verified['evidence'])
        self.assertFalse(package_attempt.exists())
        self.assertFalse(verify_attempt.exists())

    def test_verify_artifact_excludes_mutable_attempt_bookkeeping(self):
        bundle = self.root/'bundle'
        bundle.mkdir()
        archive = self.root/'release.tar.gz'
        archive.write_bytes(b'owned archive fixture')
        attempt = self.folder/'attempts/verify'
        evidence = attempt/'evidence'
        evidence.mkdir(parents=True)
        (evidence/'compiled.json').write_text('{}\n')
        result = dict(bundle=str(bundle), archive=str(archive), archive_sha256=file_state(archive)['sha256'],
                      evidence=str(evidence))
        with patch.object(community_verify, 'verify_bundle', return_value='bundle-hash'):
            before = self.runner.artifact('verify', result, self.plan)
            atomic_json(attempt/'receipt.json', dict(status='done', seconds=1))
            (attempt/'run.log').write_text('done\n')
            self.assertEqual(before, self.runner.artifact('verify', result, self.plan))
            (evidence/'compiled.json').write_text('{"tampered":true}\n')
            self.assertNotEqual(before, self.runner.artifact('verify', result, self.plan))

    def test_tar_rejects_links_traversal_and_changed_modes(self):
        bundle = self.root/'ac-deck-linux-x86_64'
        bundle.mkdir()
        (bundle/'ac-deck').write_bytes(b'owned executable fixture')
        (bundle/'ac-deck').chmod(0o755)
        archive = self.root/'package.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            stream.add(bundle, arcname=bundle.name)
        community_verify.verify_archive(archive, bundle, self.root/'extracted with spaces')
        for index, (name, kind) in enumerate((('../escape', tarfile.REGTYPE),
                                              (bundle.name+'/link', tarfile.SYMTYPE))):
            with tarfile.open(archive, 'w:gz') as stream:
                row = tarfile.TarInfo(name)
                row.type = kind
                row.linkname = '/outside'
                stream.addfile(row)
            with self.assertRaises((CycleError, ValueError)):
                community_verify.verify_archive(archive, bundle, self.root/('rejected-'+str(index)))
        self.assertFalse((self.root/'escape').exists())
        if os.name != 'nt':
            with tarfile.open(archive, 'w:gz') as stream:
                def changed_mode(row):
                    if row.isfile():
                        row.mode = 0o644
                    return row
                stream.add(bundle, arcname=bundle.name, filter=changed_mode)
            with self.assertRaisesRegex(CycleError, 'modos'):
                community_verify.verify_archive(archive, bundle, self.root/'wrong mode')

    def test_public_selection_contains_entire_standalone_workflow(self):
        names = exporter.selected_sources()
        for name in ('scripts/ciclo_entrega.py', 'scripts/ciclo_entrega_lib/common.py',
                     'scripts/ciclo_entrega_lib/community_verify.py', 'tests/test_community_cycle.py'):
            self.assertIn(name, names)
        self.assertNotIn('scripts/inventario_importacao.py', names)


if __name__ == '__main__':
    unittest.main()
