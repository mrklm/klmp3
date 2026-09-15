"""Select published updates only when their manifest declares compatibility."""
import json
import platform
import re
import urllib.request

MANIFEST = 'klmp3-update.json'


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){0,3}', value):
        raise ValueError('Invalid version')
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * (4 - len(parts))


def release_version(tag):
    if not isinstance(tag, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
        return None
    return version(tag.lstrip('v'))


def current_system():
    system = platform.system().lower()
    architecture = platform.machine().lower()
    architecture = {'amd64': 'x86_64', 'aarch64': 'arm64'}.get(architecture, architecture)
    os_version = platform.mac_ver()[0] if system == 'darwin' else platform.win32_ver()[1] if system == 'windows' else ''
    return system, architecture, os_version


def read_json(url):
    if not isinstance(url, str) or not url.startswith('https://'):
        raise ValueError('HTTPS required')
    req = urllib.request.Request(url, headers={'User-Agent': 'KLMP3-update-check', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=8) as response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError('Update response too large')
        return json.loads(data)


def compatible_asset(release, manifest, system=None):
    system_name, architecture, os_version = system or current_system()
    if not isinstance(manifest, dict) or manifest.get('schema') != 1:
        return None
    if manifest.get('version') != str(release.get('tag_name', '')).lstrip('v'):
        return None
    packages = manifest.get('packages')
    if not isinstance(packages, list):
        return None
    assets = {a.get('name'): a.get('browser_download_url') for a in release.get('assets', [])}
    extensions = {'darwin': ('.dmg', '.zip'), 'windows': ('.exe', '.zip'), 'linux': ('.AppImage', '.tar.gz')}.get(system_name, ())
    candidates = []
    for package in packages:
        if not isinstance(package, dict) or package.get('os') != system_name or package.get('arch') != architecture:
            continue
        minimum, maximum = package.get('min_os'), package.get('max_os')
        if system_name == 'darwin' and not minimum:
            continue
        try:
            if minimum and version(os_version) < version(minimum):
                continue
            if maximum and version(os_version) > version(maximum):
                continue
        except ValueError:
            continue
        name = package.get('name')
        if not isinstance(name, str) or '/' in name or '\\' in name or name not in assets:
            continue
        url = assets[name]
        if not isinstance(url, str) or not url.startswith('https://'):
            continue
        for rank, extension in enumerate(extensions):
            if name.lower().endswith(extension.lower()):
                floor = version(minimum) if minimum else (0, 0, 0, 0)
                candidates.append((tuple(-part for part in floor), rank, name, url))
                break
    if not candidates:
        return None
    _, _, name, url = sorted(candidates)[0]
    return name, url


def find_update(owner, repo, local_version, system=None, get_json=read_json):
    """Return (status, release, asset); failures raise, never report up-to-date."""
    releases = []
    for page in range(1, 11):
        batch = get_json(f'https://api.github.com/repos/{owner}/{repo}/releases?per_page=100&page={page}')
        if not isinstance(batch, list):
            raise ValueError('Invalid release list')
        releases.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError('Release history exceeds search limit')
    newer = [r for r in releases if not r.get('draft') and not r.get('prerelease')
             and release_version(r.get('tag_name')) is not None
             and release_version(r['tag_name']) > version(local_version)]
    newer.sort(key=lambda r: release_version(r['tag_name']), reverse=True)
    for release in newer:
        manifest_asset = next((a for a in release.get('assets', []) if a.get('name') == MANIFEST), None)
        if not manifest_asset:
            continue
        manifest = get_json(manifest_asset.get('browser_download_url'))
        asset = compatible_asset(release, manifest, system)
        if asset:
            return 'available', release, asset
    return ('incompatible' if newer else 'none'), None, None
