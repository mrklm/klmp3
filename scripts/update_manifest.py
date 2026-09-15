"""Describe built packages, then merge declarations into klmp3-update.json."""
import argparse
import json
from pathlib import Path
import platform
import re


def build_manifest(directory, version, target, minimum=None, maximum=None):
    systems = {'macos': 'darwin', 'windows': 'windows', 'linux': 'linux'}
    prefix, arch = target.split('-', 1)
    system = systems[prefix]
    if system == 'darwin':
        minimum = minimum or platform.mac_ver()[0]
        if not minimum:
            raise ValueError('A verified minimum macOS version is required')
    for value in (minimum, maximum):
        if value is not None and not re.fullmatch(r'\d+(?:\.\d+){0,3}', value):
            raise ValueError('Invalid OS version')
    extensions = {'darwin': ('.dmg', '.zip'), 'windows': ('.exe', '.zip'), 'linux': ('.AppImage', '.tar.gz')}[system]
    packages = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or not path.name.endswith(extensions):
            continue
        if target.lower() not in path.name.lower():
            raise ValueError(f'Package does not match target {target}: {path.name}')
        if f'-{version}-' not in path.name and f'-v{version}-' not in path.name:
            raise ValueError(f'Wrong package version: {path.name}')
        # Each build runs in its own directory containing one platform only.
        packages.append({'name': path.name, 'os': system, 'arch': arch,
                         **({'min_os': minimum} if minimum else {}),
                         **({'max_os': maximum} if maximum else {})})
    if not packages:
        raise ValueError('No packages found')
    return {'schema': 1, 'version': version, 'packages': packages}


def merge_manifests(directory, version):
    packages, names = [], set()
    for path in sorted(directory.glob('compat-*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema') != 1 or data.get('version') != version:
            raise ValueError(f'Inconsistent manifest: {path.name}')
        for package in data['packages']:
            name = package['name']
            if name in names or Path(name).name != name or not (directory / name).is_file():
                raise ValueError(f'Duplicate or missing package: {name}')
            names.add(name)
            packages.append(package)
    if not packages:
        raise ValueError('No compatibility declarations found')
    return {'schema': 1, 'version': version, 'packages': packages}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('releases'))
    parser.add_argument('--target', choices=['linux-x86_64', 'windows-x86_64', 'macos-x86_64', 'macos-arm64'])
    parser.add_argument('--variant', default='', help='Optional package family, e.g. high-sierra or catalina')
    parser.add_argument('--min-os', help='Override only with a verified OS compatibility floor')
    parser.add_argument('--max-os', help='Optional verified OS compatibility ceiling')
    args = parser.parse_args()
    version = re.search(r'^APP_VERSION = "([^"]+)"', Path('klmp3.py').read_text(encoding='utf-8'), re.M)[1]
    if args.target:
        manifest = build_manifest(args.directory, version, args.target, args.min_os, args.max_os)
        if args.variant and not re.fullmatch(r'[a-z0-9-]+', args.variant):
            raise ValueError('Invalid variant')
        suffix = '-' + args.variant if args.variant else ''
        filename = f'compat-{args.target}{suffix}.json'
    else:
        manifest = merge_manifests(args.directory, version)
        filename = 'klmp3-update.json'
    (args.directory / filename).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
