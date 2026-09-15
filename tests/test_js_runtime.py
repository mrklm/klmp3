from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import klmp3 as app
from test_audiomeans import harness


class RuntimeTests(unittest.TestCase):
    def test_bundled_quickjs_wins_without_os_version_rule(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'tools' / app._platform_tag()
            target.mkdir(parents=True)
            name = 'qjs.exe' if app.sys.platform.startswith('win') else 'qjs'
            (target / name).write_text('fixture')
            (target / name).chmod(0o755)
            with patch('klmp3._app_base_dir', return_value=folder), patch('klmp3.find_deno_tools_first') as deno:
                runtime, tool = app.find_js_runtime_tools_first()
            self.assertEqual(runtime, 'quickjs')
            self.assertEqual(tool.path, str(target / name))
            deno.assert_not_called()

    def test_deno_fallback(self):
        tool = app.ToolPath('/bundled/deno', 'TOOLS')
        with patch('klmp3._is_executable', return_value=False), patch('klmp3.find_deno_tools_first', return_value=tool):
            self.assertEqual(app.find_js_runtime_tools_first(), ('deno', tool))

    def test_os_gate(self):
        for system, mac, expected in [('darwin', '10.13.6', False), ('darwin', '10.14.6', False), ('darwin', '10.15.7', True), ('darwin', '15.1', True), ('linux', '', True), ('win32', '', True)]:
            with self.subTest(system=system, mac=mac), patch('klmp3.sys.platform', system), patch('klmp3.platform.mac_ver', return_value=(mac, (), '')):
                self.assertEqual(app.ytdlp_standalone_update_allowed(), expected)

    def test_no_network_or_install_for_legacy(self):
        with patch('klmp3.ytdlp_standalone_update_allowed', return_value=False), patch('klmp3.urllib.request.urlopen') as network, patch('klmp3.os.replace') as install:
            self.assertFalse(app.download_latest_ytdlp_to('/not-written/yt-dlp', lambda s: None))
        network.assert_not_called()
        install.assert_not_called()

    def test_legacy_ignores_previous_user_binary(self):
        with patch('klmp3.ytdlp_standalone_update_allowed', return_value=False), patch('klmp3.ytdlp_module_available', return_value=True), patch('klmp3._user_tool_path') as user, patch('klmp3.shutil.which') as path:
            self.assertIsNone(app.find_ytdlp_tools_first().path)
        user.assert_not_called()
        path.assert_not_called()

    def test_blocked_buttons_do_not_start_download_or_offer(self):
        obj = SimpleNamespace(log=lambda s: None, _error_looks_like_ytdlp_issue=lambda s: True)
        with patch('klmp3.ytdlp_standalone_update_allowed', return_value=False), patch('klmp3.messagebox.showinfo') as info, patch('klmp3.messagebox.askyesno') as ask, patch('klmp3.threading.Thread') as thread:
            app.App.update_ytdlp_for_user(obj)
            app.App._offer_ytdlp_update_after_failure(obj, 'error')
        info.assert_called_once()
        ask.assert_not_called()
        thread.assert_not_called()

    def test_download_options_api_and_cli(self):
        for runtime in ('quickjs', 'deno'):
            for mode in ('module', 'binary'):
                with self.subTest(runtime=runtime, mode=mode), tempfile.TemporaryDirectory() as folder:
                    obj = harness(mode)
                    executable = Path(folder) / 'runtime'
                    executable.write_text('fixture')
                    obj.js_runtime_name = runtime
                    obj.js_runtime_path = str(executable)
                    def api_init(options):
                        self.assertEqual(options['js_runtimes'], {runtime: {'path': str(executable)}})
                        self.assertEqual(options['remote_components'], ['ejs:github'])
                        return manager
                    manager = unittest.mock.MagicMock()
                    manager.__enter__.return_value.download.return_value = 0
                    def cli(cmd, *args, **kwargs):
                        self.assertIn(f'{runtime}:{executable}', cmd)
                        self.assertIn('ejs:github', cmd)
                        self.assertEqual('--no-js-runtimes' in cmd, runtime == 'quickjs')
                        return 0
                    with patch('yt_dlp.YoutubeDL', side_effect=api_init) as api, patch('klmp3.find_ytdlp_tools_first', return_value=app.ToolPath(None, 'MISSING')), patch('klmp3.run_subprocess', side_effect=cli) as binary:
                        obj._download_audio('https://www.youtube.com/watch?v=test', folder + '/%(title)s.%(ext)s', 'youtube', app.DL_MODE_SINGLE, False, 0)
                    self.assertEqual(api.call_count if mode == 'module' else binary.call_count, 1)
