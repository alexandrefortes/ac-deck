import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from src.launcher import community_download


class Response(io.BytesIO):
    def __init__(self, data, url='https://example.invalid/archive'):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, data, url='https://example.invalid/archive'):
        self.data, self.url = data, url

    def open(self, request, timeout):
        return Response(self.data, self.url)


class DownloadTests(unittest.TestCase):
    def test_verified_download_and_existing_file_preserved(self):
        data = b'synthetic archive'
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive.zip'
            community_download.download('https://example.invalid/archive', path, digest, opener=Opener(data))
            self.assertEqual(data, path.read_bytes())
            with self.assertRaises(FileExistsError):
                community_download.download('https://example.invalid/archive', path, digest, opener=Opener(b'other'))
            self.assertEqual(data, path.read_bytes())

    def test_unverified_download_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive.zip'
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                community_download.download('https://example.invalid/archive', path, '0' * 64,
                                            opener=Opener(b'not the selected bytes'))
            self.assertEqual(b'not the selected bytes', path.read_bytes())

    def test_http_and_insecure_redirect_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive.zip'
            with self.assertRaises(ValueError):
                community_download.download('http://example.invalid/archive', path, '0' * 64)
            with self.assertRaises(ValueError):
                community_download.download('https://example.invalid/archive', path, '0' * 64,
                                            opener=Opener(b'data', 'http://example.invalid/archive'))
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
