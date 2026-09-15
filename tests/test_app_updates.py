import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app_updates import compatible_asset, find_update, current_system
from scripts.update_manifest import build_manifest, merge_manifests
from klmp3 import App


def release(tag='v2.10.7'):
    return {'tag_name': tag, 'assets': [
        {'name': name, 'browser_download_url': 'https://example.org/' + name}
        for name in ('modern.dmg', 'catalina.dmg', 'sierra.dmg', 'arm.dmg', 'windows.zip', 'klmp3-update.json')]}


def manifest(tag='2.10.7'):
    return {'schema': 1, 'version': tag, 'packages': [
        {'name': 'modern.dmg', 'os': 'darwin', 'arch': 'x86_64', 'min_os': '15.0'},
        {'name': 'arm.dmg', 'os': 'darwin', 'arch': 'arm64', 'min_os': '15.0'},
        {'name': 'windows.zip', 'os': 'windows', 'arch': 'x86_64'},
    ]}


class UpdateTests(unittest.TestCase):
    def test_modern_release_not_offered_to_legacy(self):
        for os_version in ('10.13.6', '10.15.7', ''):
            self.assertIsNone(compatible_asset(release(), manifest(), ('darwin', 'x86_64', os_version)))

    def test_legacy_ranges(self):
        data = manifest()
        data['packages'] += [
            {'name': 'sierra.dmg', 'os': 'darwin', 'arch': 'x86_64', 'min_os': '10.13', 'max_os': '10.14.99'},
            {'name': 'catalina.dmg', 'os': 'darwin', 'arch': 'x86_64', 'min_os': '10.15', 'max_os': '14.99'},
        ]
        self.assertEqual(compatible_asset(release(), data, ('darwin', 'x86_64', '10.13.6'))[0], 'sierra.dmg')
        self.assertEqual(compatible_asset(release(), data, ('darwin', 'x86_64', '10.15.7'))[0], 'catalina.dmg')
        self.assertEqual(compatible_asset(release(), data, ('darwin', 'arm64', '15.1'))[0], 'arm.dmg')

    def test_os_arch_and_missing_metadata(self):
        self.assertEqual(compatible_asset(release(), manifest(), ('windows', 'x86_64', '10.0'))[0], 'windows.zip')
        self.assertIsNone(compatible_asset(release(), manifest(), ('linux', 'x86_64', '')))
        self.assertIsNone(compatible_asset(release(), manifest('2.10.6'), ('windows', 'x86_64', '')))
        data = manifest()
        del data['packages'][0]['min_os']
        self.assertIsNone(compatible_asset(release(), data, ('darwin', 'x86_64', '15.0')))

    def test_last_compatible_release_not_latest(self):
        older = release('v2.10.7')
        newer = release('v2.10.8')
        older['assets'][-1]['browser_download_url'] = 'https://example.org/older'
        legacy = manifest()
        legacy['packages'][0]['min_os'] = '10.15'
        def fetch(url):
            if '/releases?' in url:
                return [newer, older]
            return legacy if url.endswith('/older') else manifest('2.10.8')
        status, chosen, _ = find_update('owner', 'repo', '2.10.6', ('darwin', 'x86_64', '10.15.7'), fetch)
        self.assertEqual(status, 'available')
        self.assertEqual(chosen['tag_name'], 'v2.10.7')

    def test_absent_manifest_and_no_newer_version(self):
        rel = release()
        rel['assets'] = []
        self.assertEqual(find_update('o', 'r', '2.10.6', get_json=lambda u: [rel])[0], 'incompatible')
        self.assertEqual(find_update('o', 'r', '2.10.7', get_json=lambda u: [rel])[0], 'none')

    def test_network_failure_not_reported_as_up_to_date(self):
        with self.assertRaises(OSError):
            find_update('o', 'r', '2.10.6', get_json=lambda u: (_ for _ in ()).throw(OSError()))

    def test_drafts_prereleases_ignored(self):
        self.assertEqual(find_update('o', 'r', '2.10.6', get_json=lambda u: [dict(release(), draft=True), dict(release(), prerelease=True)])[0], 'none')

    def test_status_removes_old_click_binding(self):
        class Widget:
            def __init__(self): self.options = {}; self.bound = False
            def configure(self, **kwargs): self.options.update(kwargs)
            def bind(self, *args): self.bound = True
            def unbind(self, *args): self.bound = False
        app = SimpleNamespace(lbl_app_update=Widget(), btn_app_download=Widget())
        App._set_app_update_status(app, 'available', 'v2.10.7', ('a.dmg', 'https://example.org/a'))
        for state in ('incompatible', 'none', 'error', 'checking'):
            App._set_app_update_status(app, state)
            self.assertFalse(app.lbl_app_update.bound)
            self.assertEqual(app.btn_app_download.options['state'], 'disabled')
            self.assertIsNone(app._app_update_info['asset'])

    def test_newest_compatible_build_preferred(self):
        data = manifest()
        data['packages'].append({'name': 'catalina.dmg', 'os': 'darwin', 'arch': 'x86_64', 'min_os': '10.15'})
        self.assertEqual(compatible_asset(release(), data, ('darwin', 'x86_64', '15.7'))[0], 'modern.dmg')

    def test_release_pagination(self):
        calls = []
        def fetch(url):
            calls.append(url)
            if url.endswith('&page=1'):
                return [dict(release(), draft=True)] * 100
            if url.endswith('&page=2'):
                return [release()]
            return manifest()
        status, _, _ = find_update('o', 'r', '2.10.6', ('windows', 'x86_64', '10.0'), fetch)
        self.assertEqual(status, 'available')
        self.assertTrue(any('page=2' in u for u in calls))

    def test_generation_and_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / 'KLMP3-2.10.7-macOS-x86_64.dmg').write_bytes(b'package')
            with patch('scripts.update_manifest.platform.mac_ver', return_value=('15.7', (), '')):
                data = build_manifest(directory, '2.10.7', 'macos-x86_64')
            self.assertEqual(data['packages'][0]['min_os'], '15.7')
            (directory / 'compat-macos-x86_64.json').write_text(json.dumps(data))
            self.assertEqual(merge_manifests(directory, '2.10.7'), data)
