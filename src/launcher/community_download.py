"""Download one pinned public archive without executing its contents."""
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import file_io as safe

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


class _HttpsRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme.lower() != 'https':
            raise ValueError('Refusing a non-HTTPS download redirect')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url, destination, expected_sha256, *, opener=None):
    """Write a verified archive exclusively; preserve any pre-existing file.

    A digest establishes equality with the selected bytes, not publisher
    authentication. A failed download remains at destination for inspection.
    """
    if urlsplit(url).scheme.lower() != 'https' or not urlsplit(url).hostname:
        raise ValueError('Download URL must use HTTPS')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected SHA-256 is invalid')
    path = safe.absolute(destination)
    safe.check_components(path)
    if not path.parent.is_dir():
        raise ValueError('Download directory does not exist')
    transport = opener or build_opener(_HttpsRedirect())
    digest = hashlib.sha256()
    total = 0
    headers = {'User-Agent': 'Mozilla/5.0'}
    if urlsplit(url).hostname == 'acstuff.club':
        headers['Referer'] = 'https://acstuff.club/patch/'
    with transport.open(Request(url, headers=headers), timeout=60) as response:
        if urlsplit(response.geturl()).scheme.lower() != 'https':
            raise ValueError('Download ended at a non-HTTPS URL')
        with path.open('xb') as output:
            safe.require_reference(os.fstat(output.fileno()), path)
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError('Download exceeds the archive size limit')
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
            safe.require_reference(os.fstat(output.fileno()), path)
    observed, info = safe.hash_reference_file(path)
    if digest.hexdigest() != expected_sha256 or observed != expected_sha256 or info.st_size != total:
        raise ValueError('Downloaded archive does not match the selected SHA-256')
    return path
