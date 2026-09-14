import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

import audiomeans as am
from klmp3 import App, DL_MODE_SINGLE

EPISODE = '0ae71534-bf39-457e-b4af-ac7f95134b0d'
PLAYER = f'https://podcasts.audiomeans.fr/player-v2/example/episodes/{EPISODE}'


def page(path='https://audio.audiomeans.fr/file/test/episode.mp3?_=0'):
    return '<script>window.__INITIAL_DATA__ = ' + json.dumps({
        'episode': {'id': EPISODE, 'title': 'Un épisode', 'audio': {'path': path}},
        'podcast': {'name': 'Podcast'},
    }) + ';</script>'


def harness(mode='module'):
    obj = SimpleNamespace(
        stop_flag=threading.Event(), ytdlp_mode=mode, ytdlp_path=None,
        log=lambda msg: None, deno_path=None,
        ffmpeg_path=str(Path('tools/linux-x86_64/ffmpeg').resolve()),
        mp3_quality_var=SimpleNamespace(get=lambda: '5'),
        normalize_enabled_var=SimpleNamespace(get=lambda: False),
        fetch_cover_var=SimpleNamespace(get=lambda: False),
        _set_active_proc=lambda proc: None, _clear_active_proc=lambda proc: None,
    )
    for name in ('_download_audio', '_pipeline_download_and_convert', '_convert_audio',
                 '_safe_remove', '_cleanup_partials_for', '_probe_ytdlp_binary', '_run_subprocess_collect'):
        setattr(obj, name, getattr(App, name).__get__(obj))
    return obj


class ResolverTests(unittest.TestCase):
    def test_direct_and_fresh_each_time(self):
        with patch.object(am, '_read_html', side_effect=[page(), page('https://files.audiomeans.fr/audio/test.mp3?Signature=fresh')]) as fetch:
            first = am.resolve(PLAYER)
            second = am.resolve(PLAYER)
        self.assertEqual(fetch.call_count, 2)
        self.assertNotEqual(first['url'], second['url'])
        self.assertEqual(second['album'], 'Podcast')

    def test_embeds_and_embedly(self):
        for value in (PLAYER, PLAYER.replace('/', r'\/'), quote(PLAYER, safe=''), quote(quote(PLAYER, safe=''), safe='')):
            with self.subTest(value=value), patch.object(am, '_read_html', side_effect=[
                f'<iframe src="https://cdn.embedly.com/widgets/media.html?src={value}&amp;display_name=test"></iframe>', page()
            ]):
                self.assertEqual(am.resolve('https://www.mediapart.fr/journal/example')['id'], EPISODE)

    def test_subscriber_page_retries_with_scoped_session(self):
        jar = object()
        with patch.object(am, '_firefox_mediapart_cookies', return_value=jar), patch.object(am, '_read_html', side_effect=[
            '<html>Connexion requise</html>', f'<iframe src="{PLAYER}"></iframe>', page()
        ]) as fetch:
            self.assertEqual(am.resolve('https://www.mediapart.fr/journal/article')['id'], EPISODE)
        self.assertEqual(fetch.call_args_list[1].kwargs, {'cookie_jar': jar})
        self.assertEqual(fetch.call_args_list[2].kwargs, {'referer': 'https://www.mediapart.fr/journal/article'})

    def test_public_page_does_not_read_session(self):
        with patch.object(am, '_firefox_mediapart_cookies') as cookies, patch.object(am, '_read_html', side_effect=[f'<iframe src="{PLAYER}"></iframe>', page()]):
            am.resolve('https://www.mediapart.fr/journal/article')
        cookies.assert_not_called()

    def test_session_does_not_grant_access_reports_error(self):
        with patch.object(am, '_firefox_mediapart_cookies', return_value=object()), patch.object(am, '_read_html', return_value='<html>Connexion</html>'), self.assertRaisesRegex(am.AudiomeansError, 'après connexion'):
            am.resolve('https://www.mediapart.fr/journal/article')

    def test_cookie_domain_filter(self):
        from http.cookiejar import Cookie
        def cookie(domain):
            return Cookie(0, 'session', 'test', None, False, domain, True, domain.startswith('.'), '/', True, True, None, True, None, None, {})
        with patch('yt_dlp.cookies.extract_cookies_from_browser', return_value=[cookie('.mediapart.fr'), cookie('example.org'), cookie('mediapart.fr.example.org')]):
            jar = am._firefox_mediapart_cookies()
        self.assertEqual([c.domain for c in jar], ['.mediapart.fr'])
        self.assertFalse(am._is_mediapart('mediapart.fr.example.org'))

    def test_embedly_outer_parameters_are_not_player_parameters(self):
        player = PLAYER + '?theme=dark&download=0'
        wrapper = 'https://cdn.embedly.com/widgets/media.html?src=' + quote(player, safe='') + '&display_name=Audiomeans'
        self.assertEqual(am.find_player(f'<iframe src="{wrapper}"></iframe>'), player)

    def test_null_audio_has_specific_error(self):
        body = '<script>window.__INITIAL_DATA__ = ' + json.dumps({'episode': {'id': EPISODE, 'audio': None}}) + '</script>'
        with self.assertRaisesRegex(am.AudiomeansError, 'ne fournit aucun audio'):
            am.player_info(body, PLAYER)

    def test_embedded_player_receives_actual_page_referer(self):
        article = 'https://example.org/article'
        with patch.object(am, '_read_html', side_effect=[f'<iframe src="{PLAYER}"></iframe>', page()]) as fetch:
            info = am.resolve(article)
        self.assertEqual(fetch.call_args_list[1].kwargs, {'referer': article})
        self.assertEqual(info['http_headers'], {'Referer': article})

    def test_no_player_keeps_generic(self):
        with patch.object(am, '_read_html', return_value='<html>No player</html>'):
            self.assertIsNone(am.resolve('https://example.org/article'))

    def test_invalid_missing_and_wrong_episode(self):
        with self.assertRaises(am.AudiomeansError):
            am.resolve('https://podcasts.audiomeans.fr/player-v2/invalid')
        for body in ('<html>404</html>', page().replace(EPISODE, 'another-episode')):
            with patch.object(am, '_read_html', return_value=body), self.assertRaises(am.AudiomeansError):
                am.resolve(PLAYER)
        with patch.object(am, '_read_html', side_effect=OSError()), self.assertRaises(am.AudiomeansError):
            am.resolve(PLAYER)

    def test_exact_host_and_unchanged_signature(self):
        self.assertFalse(am.is_audiomeans('https://files.audiomeans.fr.evil.org/audio.mp3'))
        url = 'https://files.audiomeans.fr/a.mp3?Signature=a%2Fb&Expires=123'
        self.assertEqual(am.resolve(url)['url'], url)

    def test_unsupported_audio_host(self):
        with self.assertRaises(am.AudiomeansError):
            am.player_info(page('https://example.org/a.mp3'), PLAYER)

    def test_classification_regressions(self):
        for url, kind in ((PLAYER, 'single'), ('https://youtu.be/abcdefghijk', 'single'),
                          ('https://www.youtube.com/playlist?list=abc', 'playlist'),
                          ('https://www.youtube.com/watch?v=abc&list=def', 'ambiguous')):
            self.assertEqual(App._classify_url(None, url), kind)


class PipelineTests(unittest.TestCase):
    def test_module_metadata_and_existing_download(self):
        import yt_dlp
        obj = harness()
        with tempfile.TemporaryDirectory() as directory:
            def process(info, download):
                self.assertEqual(info['title'], 'Un épisode')
                Path(directory, 'Un épisode.mp3').write_bytes(b'fixture')
            with patch.object(yt_dlp.YoutubeDL, 'process_ie_result', side_effect=process) as custom:
                ok, result = obj._download_audio(PLAYER, directory + '/%(title)s.%(ext)s', 'audiomeans', DL_MODE_SINGLE, False, 0, am.player_info(page(), PLAYER))
                self.assertTrue(ok, result)
                custom.assert_called_once()
            with patch.object(yt_dlp.YoutubeDL, 'download', return_value=0) as generic:
                obj._download_audio('https://example.org/file', directory + '/%(title)s.%(ext)s', 'generic', DL_MODE_SINGLE, False, 0)
                generic.assert_called_once_with(['https://example.org/file'])

    def test_binary_info_is_temporary(self):
        obj = harness('binary')
        paths = []
        with tempfile.TemporaryDirectory() as directory:
            def run(cmd, on_line, *args, **kwargs):
                info_path = cmd[cmd.index('--load-info-json') + 1]
                paths.append(info_path)
                self.assertEqual(json.loads(Path(info_path).read_text())['id'], EPISODE)
                target = str(Path(directory, 'audio.mp3'))
                Path(target).write_bytes(b'fixture')
                on_line('[download] Destination: ' + target)
                return 0
            with patch('klmp3.find_ytdlp_tools_first', return_value=SimpleNamespace(path=None)), patch('klmp3.run_subprocess', side_effect=run):
                self.assertTrue(obj._download_audio(PLAYER, directory + '/%(title)s.%(ext)s', 'audiomeans', DL_MODE_SINGLE, False, 0, am.player_info(page(), PLAYER))[0])
        self.assertFalse(os.path.exists(paths[0]))

    def test_cancelled_download_does_not_start(self):
        import yt_dlp
        obj = harness()
        obj.stop_flag.set()
        with patch.object(yt_dlp.YoutubeDL, 'process_ie_result') as process:
            ok, _ = obj._download_audio(PLAYER, '/tmp/unused.%(ext)s', 'audiomeans', DL_MODE_SINGLE, False, 0, am.player_info(page(), PLAYER))
        self.assertFalse(ok)
        process.assert_not_called()

    def test_html_disguised_as_audio_is_rejected_and_cleaned(self):
        obj = harness()
        if not os.path.isfile(obj.ffmpeg_path):
            self.skipTest('Bundled ffmpeg unavailable')
        with tempfile.TemporaryDirectory() as directory:
            def download(url, template, *args, **kwargs):
                target = Path(template).parent / 'Not audio.mp3'
                target.write_text('<html>Access denied</html>')
                return True, str(target)
            with patch('klmp3.resolve_audiomeans', return_value=am.player_info(page(), PLAYER)), patch.object(obj, '_download_audio', side_effect=download):
                ok, _ = obj._pipeline_download_and_convert(PLAYER, directory, 'mp3', 'generic', DL_MODE_SINGLE, False, 0)
            self.assertFalse(ok)
            self.assertFalse(list(Path(directory).iterdir()))

    def test_real_conversion_preserves_existing_files(self):
        obj = harness()
        if not os.path.isfile(obj.ffmpeg_path):
            self.skipTest('Bundled ffmpeg unavailable')
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory, 'fixture.mp3')
            subprocess.run([obj.ffmpeg_path, '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.2', str(fixture)], check=True)
            existing = Path(directory, 'Un épisode.mp3')
            existing.write_bytes(b'keep existing')
            other = Path(directory, 'Un épisode (02).m4a')
            other.write_bytes(b'keep other format')
            def download(url, template, *args, **kwargs):
                target = Path(template).parent / 'Un épisode.mp3'
                target.write_bytes(fixture.read_bytes())
                return True, str(target)
            with patch('klmp3.resolve_audiomeans', return_value=am.player_info(page(), PLAYER)), patch.object(obj, '_download_audio', side_effect=download):
                ok, message = obj._pipeline_download_and_convert(PLAYER, directory, 'mp3', 'generic', DL_MODE_SINGLE, False, 0)
            self.assertTrue(ok, message)
            final = Path(directory, 'Un épisode (02).mp3')
            subprocess.run([obj.ffmpeg_path, '-v', 'error', '-i', str(final), '-f', 'null', '-'], check=True)
            self.assertEqual(existing.read_bytes(), b'keep existing')
            self.assertEqual(other.read_bytes(), b'keep other format')
            self.assertFalse(list(Path(directory).glob('*.klmp3-source')))


if __name__ == '__main__':
    unittest.main()
