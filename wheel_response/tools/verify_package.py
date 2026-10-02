"""Read-only SHA256 verification of an extracted delivery package; stdlib only."""
import argparse
import csv
import hashlib
import pathlib
import sys

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default=str(pathlib.Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    manifest = root/'delivery_manifest_sha256.csv'
    failures = []
    count = 0
    with manifest.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            count += 1
            path = (root/row['path']).resolve()
            if not path.is_relative_to(root):
                failures.append((row['path'], 'outside_package'))
            elif not path.is_file():
                failures.append((row['path'], 'missing'))
            elif path.stat().st_size != int(row['bytes']) or sha256(path) != row['sha256']:
                failures.append((row['path'], 'size_or_sha256_mismatch'))
    for path, reason in failures:
        print(reason, path)
    print(f'Checked {count} payload files; failures={len(failures)}')
    return 1 if failures else 0

if __name__ == '__main__':
    sys.exit(main())
