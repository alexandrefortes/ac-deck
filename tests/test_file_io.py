"""Arquivos temporários autorais; não acessam referências ou dados do jogador."""

import hashlib
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.launcher import file_io


class FileIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.source = self.base / "reference"
        self.project.mkdir()
        (self.source / "content").mkdir(parents=True)
        (self.source / "content/car.dat").write_bytes(b"synthetic car\x00\xff")

    def hardlink(self, target, link):
        try:
            os.link(target, link)
        except OSError as error:
            self.skipTest(f"Host não permite criar hardlink na fixture temporária: {error}")

    def link_on_read(self, path, target, alias):
        """Cria vínculo real somente na fixture quando seu conteúdo é lido."""
        original_open = file_io.open_reference
        test = self

        class LinkedOnRead:
            def __init__(self, stream):
                self.stream = stream
                self.linked = False

            def read(self, size=-1):
                block = self.stream.read(size)
                if block and not self.linked:
                    test.hardlink(target, alias)
                    self.linked = True
                return block

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

        def open_with_read_link(value):
            stream, info = original_open(value)
            return (LinkedOnRead(stream), info) if value == path else (stream, info)

        return patch.object(file_io, "open_reference", side_effect=open_with_read_link)

    def test_reparse_attribute_is_rejected_without_a_windows_fixture(self):
        info = type("SyntheticStat", (), {"st_mode": stat.S_IFDIR,
                                           "st_file_attributes": file_io.REPARSE_POINT})()
        self.assertTrue(file_io.linked(info))

    def test_generic_hash_still_reads_own_hardlinked_file_but_reference_hash_refuses_it(self):
        target = self.project / "own-code.py"
        target.write_bytes(b"# synthetic authored code\n")
        self.hardlink(target, self.base / "linked-own-code.py")
        self.assertFalse(file_io.linked(target.lstat()))
        self.assertEqual(file_io.hash_file(target)[0], hashlib.sha256(target.read_bytes()).hexdigest())
        with self.assertRaisesRegex(file_io.SafetyError, "nlink=1.*nlink=2"):
            file_io.hash_reference_file(target)

    def test_reference_hash_refuses_real_hardlink_created_during_read(self):
        target = self.source / "content/car.dat"
        with self.link_on_read(target, target, self.base / "linked-during-hash.dat"):
            with self.assertRaisesRegex(file_io.SafetyError, "nlink=1.*nlink=2"):
                file_io.hash_reference_file(target)

    def test_reference_hash_refuses_descriptor_nlink_change_even_if_path_remains_single(self):
        target = self.source / "content/car.dat"
        original_fstat = os.fstat
        calls = 0

        def linked_after_read(descriptor):
            nonlocal calls
            info = original_fstat(descriptor)
            calls += 1
            if calls == 2:
                return SimpleNamespace(st_mode=info.st_mode, st_nlink=2,
                                       st_file_attributes=getattr(info, "st_file_attributes", 0))
            return info

        with patch.object(os, "fstat", side_effect=linked_after_read):
            with self.assertRaisesRegex(file_io.SafetyError, "nlink=1.*nlink=2"):
                file_io.hash_reference_file(target)
        self.assertEqual(target.stat().st_nlink, 1)

    def test_copy_refuses_source_hardlinked_during_read(self):
        source = self.source / "content/car.dat"
        target = self.project / "local/input/copy/car.dat"
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        with self.link_on_read(source, source, self.base / "linked-copy-source.dat"):
            with self.assertRaisesRegex(file_io.SafetyError, "nlink=1.*nlink=2"):
                file_io.copy_verified(source, target, expected)
        self.assertTrue(target.is_file())

    def test_copy_refuses_destination_hardlinked_during_read(self):
        source = self.source / "content/car.dat"
        target = self.project / "local/input/copy/car.dat"
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        with self.link_on_read(source, target, self.base / "linked-copy-target.dat"):
            with self.assertRaisesRegex(file_io.SafetyError, "nlink=1.*nlink=2"):
                file_io.copy_verified(source, target, expected)
        self.assertEqual(target.stat().st_nlink, 2)

    def test_json_writers_preserve_utf8_indentation_and_trailing_newline(self):
        for writer in (file_io.write_json, file_io.write_new_json):
            with self.subTest(writer=writer.__name__):
                target = self.project / (writer.__name__ + '.json')
                writer(target, {"name": "ação"})
                self.assertEqual(target.read_bytes(), '{\n  "name": "ação"\n}\n'.encode('utf-8'))

    def test_json_writers_preserve_existing_file_on_collision(self):
        for writer in (file_io.write_json, file_io.write_new_json):
            with self.subTest(writer=writer.__name__):
                target = self.project / (writer.__name__ + '.json')
                target.write_bytes(b'existing document')
                with self.assertRaises(FileExistsError):
                    writer(target, {"replacement": True})
                self.assertEqual(target.read_bytes(), b'existing document')

    def test_validated_json_rejects_linked_ancestor_while_package_writer_preserves_its_contract(self):
        alias = self.base / 'linked-project'
        try:
            alias.symlink_to(self.project, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Host não permite criar link simbólico: {error}")
        file_io.write_new_json(alias / 'package.json', {"name": "ação"})
        self.assertEqual((self.project / 'package.json').read_bytes(),
                         '{\n  "name": "ação"\n}\n'.encode('utf-8'))
        with self.assertRaisesRegex(file_io.SafetyError, 'Link'):
            file_io.write_json(alias / 'validated.json', {"name": "ação"})
        self.assertFalse((self.project / 'validated.json').exists())


if __name__ == "__main__":
    unittest.main()
