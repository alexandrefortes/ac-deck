import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import preparar_fontes_dependencias as sources


class DependencySourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root / 'licenses/dependency-sources.json'
        self.manifest.parent.mkdir()
        self.data = b'source archive bytes\n'
        self.row = {'path': 'sources/example.tar.xz', 'url': 'https://example.invalid/source',
                    'sha256': hashlib.sha256(self.data).hexdigest(), 'size_bytes': len(self.data)}
        self.output = self.root / 'collection'
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({'schema_version': 1, 'files': [self.row]}))

    def download(self, url, target, expected, **kwargs):
        target.write_bytes(self.data)

    def test_download_verify_and_reuse_without_network(self):
        with patch.object(sources.community_download, 'download', side_effect=self.download) as call:
            sources.collect(self.manifest, self.output)
            sources.collect(self.manifest, self.output)
            self.assertEqual(call.call_count, 1)
        self.assertEqual((self.output / self.row['path']).read_bytes(), self.data)

    def test_wrong_existing_file_is_preserved(self):
        target = self.output / self.row['path']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'owned data')
        with patch.object(sources.community_download, 'download') as call:
            with self.assertRaises(ValueError):
                sources.collect(self.manifest, self.output)
            call.assert_not_called()
        self.assertEqual(target.read_bytes(), b'owned data')

    def test_invalid_size_download_never_publishes(self):
        self.row['size_bytes'] += 1
        self.write_manifest()
        with patch.object(sources.community_download, 'download', side_effect=self.download):
            with self.assertRaises(ValueError):
                sources.collect(self.manifest, self.output)
        self.assertFalse((self.output / self.row['path']).exists())

    def test_unsafe_or_ambiguous_inventory_is_rejected_before_download(self):
        original = dict(self.row)
        for changes in ({'path': '../escape'}, {'url': 'http://example.invalid/source'},
                        {'sha256': None}, {'size_bytes': True}, {'repository_path': 'licenses/notice'}):
            with self.subTest(changes=changes):
                self.row = {**original, **changes}
                self.write_manifest()
                with patch.object(sources.community_download, 'download') as call:
                    with self.assertRaises((ValueError, sources.safe.SafetyError)):
                        sources.collect(self.manifest, self.output)
                    call.assert_not_called()

    def test_repository_notice_and_exclusive_source_archive(self):
        notice = self.root / 'licenses/notice.txt'
        notice.write_bytes(self.data)
        self.row.pop('url')
        self.row['repository_path'] = 'licenses/notice.txt'
        self.write_manifest()
        sources.collect(self.manifest, self.output)
        archive = self.root / 'sources.tar.gz'
        result = sources.package(self.manifest, self.output, archive)
        with tarfile.open(archive) as stream:
            self.assertEqual(stream.extractfile('ac-deck-dependency-sources/' + self.row['path']).read(), self.data)
            self.assertEqual(stream.getnames(), ['ac-deck-dependency-sources/inventory.json',
                                                'ac-deck-dependency-sources/' + self.row['path']])
            self.assertEqual(stream.extractfile('ac-deck-dependency-sources/inventory.json').read(),
                             self.manifest.read_bytes())
        self.assertEqual(result['archive_sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError):
            sources.package(self.manifest, self.output, archive)

    def test_verify_only_missing_does_not_fetch(self):
        with patch.object(sources.community_download, 'download') as call:
            with self.assertRaises(ValueError):
                sources.collect(self.manifest, self.output, verify_only=True)
            call.assert_not_called()

    def test_changed_source_during_tar_write_is_rejected(self):
        with patch.object(sources.community_download, 'download', side_effect=self.download):
            sources.collect(self.manifest, self.output)
        original = tarfile.TarFile.addfile
        def mutate_then_add(archive, member, stream=None):
            if member.name.endswith(self.row['path']):
                (self.output / self.row['path']).write_bytes(b'x' * len(self.data))
            return original(archive, member, stream)
        with patch.object(tarfile.TarFile, 'addfile', mutate_then_add):
            with self.assertRaises(ValueError):
                sources.package(self.manifest, self.output, self.root/'mutated.tar.gz')


if __name__ == '__main__':
    unittest.main()
