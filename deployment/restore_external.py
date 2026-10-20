"""Restore only a hash-locked original fixture archive into a new directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--archive', type=Path)
    source.add_argument('--url', help='Explicit HTTPS archive location supplied by the data owner')
    parser.add_argument('--dest', type=Path, required=True, help='New empty destination; refuses existing directories')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Do not use Python -O: identity and extraction assertions must remain enabled')
    manifest = json.loads(Path(__file__).with_name('b_h150_fixture_manifest.json').read_text())
    if args.dest.exists():
        parser.error('Destination already exists; preserve previous evidence')
    if args.url:
        if not args.url.startswith('https://'):
            parser.error('Download requires HTTPS')
        archive = args.dest.with_name(args.dest.name + '.download.tar.gz')
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open('xb') as output, urllib.request.urlopen(args.url) as response:
            for chunk in iter(lambda: response.read(2**20), b''):
                output.write(chunk)
    else:
        archive = args.archive
    assert archive.stat().st_size == manifest['archive']['bytes'], 'ARCHIVE_SIZE'
    assert sha(archive) == manifest['archive']['sha256'], 'ARCHIVE_SHA256'
    expected = {r['path']: r for r in manifest['files']}
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        assert len(members) == len(expected) and len({m.name for m in members}) == len(members), 'MEMBER_COUNT'
        for item in members:
            path = PurePosixPath(item.name)
            assert item.isfile() and item.name in expected and not path.is_absolute() and '..' not in path.parts, 'UNSAFE_MEMBER'
            assert item.size == expected[item.name]['bytes'], 'MEMBER_SIZE'
        args.dest.mkdir(parents=True, exist_ok=False)
        for item in members:
            dest = args.dest / item.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with bundle.extractfile(item) as source, dest.open('xb') as output:
                for chunk in iter(lambda: source.read(2**20), b''):
                    output.write(chunk)
                    h.update(chunk)
            assert h.hexdigest() == expected[item.name]['sha256'], 'MEMBER_SHA256:' + item.name
    print(json.dumps(dict(status='PASS', files=len(expected), destination=str(args.dest.resolve()), archive_sha256=manifest['archive']['sha256'])))


if __name__ == '__main__':
    main()
