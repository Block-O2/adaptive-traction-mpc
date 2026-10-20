"""Verify or archive a root-specific external-data CSV; restore verified archives.

Never removes source data. All write destinations must be new.
"""
import argparse
import csv
import hashlib
from pathlib import Path, PurePosixPath
import tarfile


def sha(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(2**20), b''):
        h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'pack', 'restore'])
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True, help='Source root for verify/pack; new destination root for restore')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--archive-sha256', help='Required independent archive identity for restore')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Python -O is forbidden')
    with args.index.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len({r['path'] for r in rows}) == len(rows), 'DUPLICATE_PATH'
    for row in rows:
        p = PurePosixPath(row['path'])
        assert p.parts and not p.is_absolute() and '..' not in p.parts, 'UNSAFE_INDEX_PATH'
    if args.action in ('verify', 'pack'):
        root = args.root.resolve()
        for row in rows:
            p = root / row['path']
            assert not p.is_symlink() and p.resolve().is_relative_to(root), 'OUTSIDE_ROOT'
            assert p.stat().st_size == int(row['bytes']), 'SIZE:' + row['path']
            with p.open('rb') as stream:
                assert sha(stream) == row['sha256'], 'SHA256:' + row['path']
        if args.action == 'pack':
            assert args.archive and not args.archive.exists(), 'NEW_ARCHIVE_REQUIRED'
            args.archive.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(args.archive, 'x:gz', compresslevel=3) as bundle:
                for row in rows:
                    bundle.add(root / row['path'], arcname=row['path'], recursive=False)
            verify_bundle(args.archive, rows)
            with args.archive.open('rb') as stream:
                print('ARCHIVE_SHA256', sha(stream))
    else:
        assert args.archive and args.archive_sha256 and not args.root.exists(), 'NEW_DEST_AND_ARCHIVE_IDENTITY_REQUIRED'
        with args.archive.open('rb') as stream:
            assert sha(stream) == args.archive_sha256, 'ARCHIVE_SHA256'
        verify_bundle(args.archive, rows, args.root)
    print('PASS', args.action, len(rows), 'files')


def verify_bundle(path, rows, dest=None):
    expected = {r['path']: r for r in rows}
    with tarfile.open(path, 'r:gz') as bundle:
        items = bundle.getmembers()
        assert len(items) == len(expected) and len({m.name for m in items}) == len(items), 'MEMBER_COUNT'
        for item in items:
            assert item.isfile() and item.name in expected and item.size == int(expected[item.name]['bytes']), 'MEMBER_IDENTITY'
        if dest:
            dest.mkdir(parents=True, exist_ok=False)
        for item in items:
            if dest:
                target = dest / item.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(item) as source, target.open('xb') as output:
                    h = hashlib.sha256()
                    for chunk in iter(lambda: source.read(2**20), b''):
                        h.update(chunk)
                        output.write(chunk)
                    assert h.hexdigest() == expected[item.name]['sha256'], 'MEMBER_SHA256'
            else:
                with bundle.extractfile(item) as stream:
                    assert sha(stream) == expected[item.name]['sha256'], 'MEMBER_SHA256'


if __name__ == '__main__':
    main()
