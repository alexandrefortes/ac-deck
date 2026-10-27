"""Community distribution boundaries use only owned fixtures; no compiler or media."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_launcher_linux as builder
from src.launcher import rogue_rewards, rogue_toasty_assets


class CommunityBuildTests(unittest.TestCase):
    def test_private_payload_options_are_rejected_before_reading_any_inputs(self):
        options = ('csp_zip', 'gt5_zip', 'bacc_dir', 'reuse_delivery',
                   'toasty_assets', 'rogue_album_assets')
        for option in options:
            with self.subTest(option=option), ExitStack() as stack:
                guards = [stack.enter_context(patch.object(owner, name)) for owner, name in
                          ((builder.Path, 'resolve'), (builder, 'digest'),
                           (builder.csp, 'digest'), (builder.csp, 'unpack'),
                           (builder.gt5_camera, 'inspect'), (builder.bacc_camera, 'inspect'),
                           (builder.importlib.metadata, 'version'), (builder, 'command'))]
                with self.assertRaisesRegex(ValueError, 'Community builds cannot include private'):
                    builder.build('community-fixture', Path('/must-not-read-native'),
                                  community=True, **{option: Path('/must-not-read-private')})
                for guard in guards:
                    guard.assert_not_called()

    def test_community_bundle_has_no_private_payload_and_keeps_source_provenance(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            (root/'src').mkdir()
            (root/'src/fixture.py').write_text('# Owned production fixture\n')
            (root/'licenses').mkdir()
            (root/'licenses/ACC-DualSense-Feedback.txt').write_text('Owned notice fixture\n')
            native = root/'native'
            native.mkdir()
            (native/'libSDL2-2.0.so.0').write_bytes(b'owned native fixture')
            font = root/'owned-font.ttf'
            font.write_bytes(b'owned licensed font fixture')
            notices = root/'notices'
            notices.mkdir()
            (notices/'runtime.txt').write_text('Owned SDK notice fixture\n')

            def command(*args, **kwargs):
                if args[:2] == ('readelf', '-d'):
                    return SimpleNamespace(stdout='(SONAME) Library soname: [libSDL2-2.0.so.0]\n')
                self.assertEqual((builder.sys.executable, '-m', 'PyInstaller'), args[:3])
                name = args[args.index('--name')+1]
                destination = Path(args[args.index('--distpath')+1])/name
                destination.mkdir(parents=True)
                (destination/name).write_bytes(b'owned compiled-result fixture')
                (destination/'_internal').mkdir()
                return SimpleNamespace(stdout='')

            stack.enter_context(patch.object(builder, 'ROOT', root))
            stack.enter_context(patch.object(builder, 'COMMUNITY_SOURCES', ('src/fixture.py',)))
            stack.enter_context(patch.object(builder, 'CSP_DOCS', ('docs/absent-private-manual.md',)))
            stack.enter_context(patch.object(builder.sys, 'platform', 'linux'))
            stack.enter_context(patch.object(builder.platform, 'machine', return_value='x86_64'))
            stack.enter_context(patch.object(builder.importlib.metadata, 'version', return_value='owned-fixture'))
            stack.enter_context(patch.object(builder.importlib.metadata, 'distribution',
                                            return_value=SimpleNamespace(version='owned-fixture', files=[])))
            stack.enter_context(patch.object(builder, 'command', side_effect=command))
            private_calls = [stack.enter_context(patch.object(owner, name,
                                      side_effect=AssertionError('Private payload must not be read')))
                             for owner, name in ((rogue_toasty_assets, 'load_distribution'),
                                                 (rogue_rewards, 'load_album_distribution'),
                                                 (builder, 'bundle_toasty_assets'),
                                                 (builder, 'bundle_rogue_album_assets'),
                                                 (builder, 'reuse_static_payload'),
                                                 (builder.csp, 'unpack'),
                                                 (builder.font_support, 'bundle'))]
            with redirect_stdout(io.StringIO()):
                result = builder.build('community-fixture', native, font=font,
                                       licenses_dir=notices, community=True)
            bundle = Path(result['bundle'])
            self.assertEqual('ac-deck-linux-x86_64', bundle.name)
            self.assertEqual('ac-deck-linux-x86_64.tar.gz', Path(result['archive']).name)
            self.assertTrue((bundle/'ac-deck').is_file())
            info = json.loads((bundle/'build-info.json').read_text())
            self.assertEqual('community', info['distribution'])
            self.assertEqual('ac-deck', info['public_name'])
            self.assertIn('no game, DLC', info['content_policy'])
            self.assertEqual({'src/fixture.py': builder.digest(root/'src/fixture.py')},
                             info['source_sha256'])
            for field in ('csp', 'csp_fonts', 'gt5_camera', 'bacc_cameras', 'rogue_toasty_assets',
                          'rogue_album_assets', 'reused_payload_manifest'):
                self.assertIsNone(info[field])
            for name in ('assets', 'csp', 'csp-fonts', 'mods', 'manual', 'game', 'local'):
                self.assertFalse((bundle/name).exists(), name)
            self.assertTrue((bundle/'licenses/sdk/runtime.txt').is_file())
            readme = (bundle/'LEIA-ME.txt').read_text()
            self.assertIn('./ac-deck --help', readme)
            self.assertNotIn('/papao', readme)
            for call in private_calls:
                call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
