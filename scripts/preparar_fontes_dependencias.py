#!/usr/bin/env python3
"""Collect the explicitly inventoried dependency sources without executing them."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
from urllib.request import BaseHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.launcher import community_download
from src.launcher import file_io as safe


class _SourceHeaders(BaseHandler):
    def https_request(self, request):
        request.add_header('User-Agent', 'Python-urllib/' + '.'.join(map(str, sys.version_info[:2])))
        return request


def inventory(path):
    payload, digest = safe.read_document(path)
    if payload.get('schema_version') != 1 or not isinstance(payload.get('files'), list):
        raise ValueError('Unsupported dependency source inventory')
    paths = set()
    for row in payload['files']:
        if not isinstance(row, dict):
            raise ValueError('Invalid artifact record')
        name = safe.relative_file(row.get('path'))
        if name in paths or name in ('inventory.json', 'collection.json'):
            raise ValueError('Duplicate or reserved artifact path')
        paths.add(name)
        if not isinstance(row.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('Invalid artifact SHA-256')
        size = row.get('size_bytes')
        if type(size) is not int or not 0 < size <= community_download.MAX_ARCHIVE_BYTES:
            raise ValueError('Invalid artifact size')
        if ('url' in row) == ('repository_path' in row):
            raise ValueError('Select exactly one artifact origin')
        if 'url' in row:
            if not isinstance(row['url'], str):
                raise ValueError('Invalid artifact URL')
            address = urlsplit(row['url'])
            if address.scheme != 'https' or not address.hostname or address.username or address.password:
                raise ValueError('Artifact URL must use HTTPS without credentials')
        elif 'repository_path' in row:
            safe.relative_file(row['repository_path'])
        else:
            raise ValueError('Artifact origin is missing')
    return payload, digest


def verify(path, row):
    digest, info = safe.hash_reference_file(path)
    if digest != row['sha256'] or info.st_size != row['size_bytes']:
        raise ValueError('Artifact differs from inventory: ' + row['path'])
    return info


def collect(manifest, destination, *, verify_only=False):
    manifest = safe.absolute(manifest)
    payload, manifest_hash = inventory(manifest)
    destination = safe.absolute(destination)
    safe.check_components(destination)
    destination.mkdir(parents=True, exist_ok=True)
    def obtain(row):
        target = destination / row['path']
        safe.check_components(target)
        if target.exists():
            verify(target, row)
            return
        if verify_only:
            raise ValueError('Missing artifact: ' + row['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        safe.check_components(target)
        if 'repository_path' in row:
            source = manifest.parent.parent / row['repository_path']
            verify(source, row)
            safe.copy_verified(source, target, row['sha256'])
        else:
            with tempfile.TemporaryDirectory(prefix='.dependency-', dir=target.parent) as scratch:
                temporary = Path(scratch) / 'download'
                opener = build_opener(community_download._HttpsRedirect(), _SourceHeaders())
                community_download.download(row['url'], temporary, row['sha256'], opener=opener)
                verify(temporary, row)
                safe.copy_verified(temporary, target, row['sha256'])
        verify(target, row)
        print('verified ' + row['path'], flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(obtain, payload['files']))
    return payload, manifest_hash


def package(manifest, destination, archive):
    payload, manifest_hash = collect(manifest, destination, verify_only=True)
    manifest_bytes = Path(manifest).read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_hash:
        raise ValueError('Inventory changed before packaging')
    archive = safe.absolute(archive)
    safe.check_components(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=1) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as output:
                member = tarfile.TarInfo('ac-deck-dependency-sources/inventory.json')
                member.size, member.mode = len(manifest_bytes), 0o644
                output.addfile(member, io.BytesIO(manifest_bytes))
                for row in payload['files']:
                    source = destination / row['path']
                    before = verify(source, row)
                    stream, opened = safe.open_reference(source)
                    if safe.signature(before) != safe.signature(opened):
                        stream.close()
                        raise ValueError('Source changed before packaging')
                    member = tarfile.TarInfo('ac-deck-dependency-sources/' + row['path'])
                    member.size, member.mode = before.st_size, 0o644
                    with stream:
                        output.addfile(member, stream)
                        safe.require_reference(opened, source)
    expected = {'ac-deck-dependency-sources/' + row['path']: row for row in payload['files']}
    expected['ac-deck-dependency-sources/inventory.json'] = {
        'sha256': manifest_hash, 'size_bytes': len(manifest_bytes)}
    with tarfile.open(archive, mode='r|gz') as source:
        for member in source:
            if not member.isfile() or member.name not in expected:
                raise ValueError('Unexpected source archive member')
            row = expected.pop(member.name)
            digest = hashlib.sha256()
            with source.extractfile(member) as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
            if digest.hexdigest() != row['sha256'] or member.size != row['size_bytes']:
                raise ValueError('Source archive member differs from inventory: ' + member.name)
    if expected or hashlib.sha256(Path(manifest).read_bytes()).hexdigest() != manifest_hash:
        raise ValueError('Incomplete archive or changed inventory')
    archive_hash, info = safe.hash_reference_file(archive)
    return {'inventory_sha256': manifest_hash, 'archive_sha256': archive_hash,
            'archive_bytes': info.st_size, 'files': len(payload['files']),
            'legal_approval': False, 'published': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', '--inventory', dest='inventory', type=Path,
                        default=ROOT / 'licenses/dependency-sources.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--archive', type=Path, help='Create and verify a new source archive')
    args = parser.parse_args(argv)
    try:
        payload, digest = collect(args.inventory, args.output, verify_only=args.verify_only)
        result = package(args.inventory, args.output, args.archive) if args.archive else {
            'inventory_sha256': digest, 'files': len(payload['files']), 'verified': True}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, safe.SafetyError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
