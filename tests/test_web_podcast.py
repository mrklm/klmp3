import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

import web_podcast as web
from test_audiomeans import harness
from klmp3 import DL_MODE_SINGLE, DL_MODE_PLAYLIST

BASE = 'https://www.blast-info.fr/podcasts/series'
AUDIO = 'https://static.example.org/one.mp3'
RSS = '''<rss><channel><title>Série</title>
<item><title>Deux</title><enclosure url="https://static.example.org/two.mp3" type="audio/mpeg"/></item>
<item><title>Un</title><enclosure url="https://static.example.org/one.mp3" type="audio/mpeg"/></item>
</channel></rss>'''


def html(records, extra=''):
    return '<title>Podcast</title><script type="application/json">' + json.dumps(records) + '</script>' + extra


def record(slug='one', url=AUDIO):
    return {'slug': slug, 'title': slug, 'audio_url': url}


class ExtractTests(unittest.TestCase):
    def resolve(self, source, url=BASE, feed=RSS):
        with patch.object(web, 'fetch', side_effect=[source, feed]):
            return web.resolve(url)

    def test_jsonld_m4a_with_no_site_rule(self):
        source = '<script type="application/ld+json">' + json.dumps({'@graph': [{'mainEntity': {'@type': 'AudioObject', 'contentUrl': 'https://media.example.org/a.m4a', 'duration': 'PT58M52S'}}]}) + '</script>'
        info = self.resolve(source, 'https://example.org/episode')
        self.assertEqual(info['ext'], 'm4a')
        self.assertEqual(info['duration'], 3532)

    def test_episode_selected_before_recommendations(self):
        result = self.resolve(html([record('two', 'https://static.example.org/two.mp3'), record()]), BASE + '/one')
        self.assertEqual(result['url'], AUDIO)

    def test_missing_episode_not_replaced(self):
        with self.assertRaises(web.PodcastError):
            self.resolve(html([record()]), BASE + '/missing')

    def test_rss_preferred_and_reordered_to_page(self):
        source = html([record(), record('two', 'https://static.example.org/two.mp3')], '<a href="https://api.example.org/series/rss.xml">RSS</a><a href="https://api.example.org/rss.xml">Global RSS</a>')
        info = self.resolve(source)
        self.assertEqual(info['title'], 'Série')
        self.assertEqual([e['title'] for e in info['entries']], ['Un', 'Deux'])

    def test_feed_fallback_to_html(self):
        info = self.resolve(html([record()], '<link type="application/rss+xml" href="/series/rss.xml">'), feed=OSError())
        self.assertEqual(info['entries'][0]['url'], AUDIO)

    def test_nuxt_indexed_table_and_escaped_slashes(self):
        table = [{"audio_url": 1, "slug": 2, "title": 3}, AUDIO, 'one', 'Titre']
        source = '<script id="__NUXT_DATA__" type="application/json">' + json.dumps(table).replace('/', r'\u002F') + '</script>'
        self.assertEqual(self.resolve(source, BASE + '/one')['url'], AUDIO)

    def test_audio_element(self):
        info = self.resolve('<title>Episode</title><audio><source src="/a.ogg"></audio>', 'https://example.org/e')
        self.assertEqual(info['url'], 'https://example.org/a.ogg')

    def test_no_audio_and_invalid_url(self):
        self.assertIsNone(self.resolve('<html>Nothing</html>', 'https://example.org'))
        self.assertIsNone(web.resolve('file:///tmp/file'))
        with self.assertRaises(web.PodcastError):
            self.resolve('<html>Nothing</html>')

    def test_rss_invalid_or_empty(self):
        for source in ('<invalid>', '<rss><channel/></rss>'):
            with self.assertRaises(web.PodcastError):
                web.rss_info(source, BASE)

    def test_direct_rss(self):
        self.assertEqual(len(self.resolve(RSS)['entries']), 2)

    def test_general_rss_directory_not_followed(self):
        with patch.object(web, 'fetch', return_value='<a href="/rss">RSS</a>') as fetch:
            self.assertIsNone(web.resolve('https://example.org/series'))
        self.assertEqual(fetch.call_count, 1)

    def test_non_audio_url_rejected(self):
        self.assertIsNone(web.audio_info({'audio_url': 'javascript:alert(1)'}, BASE))
        self.assertIsNone(web.audio_info({'audio_url': '/page.html'}, BASE))


class CollectionTests(unittest.TestCase):
    def test_metadata_survives_real_mp3_conversion(self):
        from mutagen import File as AudioFile
        obj = harness()
        if not Path(obj.ffmpeg_path).is_file():
            self.skipTest('Bundled ffmpeg unavailable')
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'fixture.mp3'
            subprocess.run([obj.ffmpeg_path, '-v', 'error', '-f', 'lavfi', '-i', 'sine=duration=0.2', str(fixture)], check=True)
            info = web.audio_info(record(), BASE)
            info.update(artist='Auteur', album='Série', track='Titre original')
            def download(url, template, *args, **kwargs):
                target = Path(template).parent / 'episode.mp3'
                target.write_bytes(fixture.read_bytes())
                return True, str(target)
            with patch.object(obj, '_download_audio', side_effect=download):
                ok, message = obj._pipeline_download_and_convert(BASE, directory, 'mp3', 'web_podcast', DL_MODE_SINGLE, False, 0, audio_info=info)
            self.assertTrue(ok, message)
            tags = AudioFile(Path(directory) / 'episode.mp3', easy=True)
            self.assertEqual(tags['title'], ['Titre original'])
            self.assertEqual(tags['artist'], ['Auteur'])
            self.assertEqual(tags['album'], ['Série'])

    def test_single_playlist_limit_and_order(self):
        for mode, limit, count in ((DL_MODE_SINGLE, False, 1), (DL_MODE_PLAYLIST, False, 3), (DL_MODE_PLAYLIST, True, 2)):
            with self.subTest(mode=mode, limit=limit), tempfile.TemporaryDirectory() as directory:
                obj = harness()
                entries = [web.audio_info(record(str(n)), BASE) for n in range(3)]
                seen = []
                def download(url, template, *args, **kwargs):
                    info = kwargs['audio_info']
                    seen.append(info['id'])
                    target = Path(template).parent / (info['title'] + '.mp3')
                    target.write_bytes(b'fixture')
                    return True, str(target)
                def convert(source, fmt):
                    target = Path(source).with_suffix('.mp3')
                    target.write_bytes(b'converted')
                    return True, str(target)
                with patch('klmp3.resolve_audiomeans', return_value=None), patch('klmp3.resolve_web_podcast', return_value={'title': 'Série', 'entries': entries}), patch.object(obj, '_download_audio', side_effect=download), patch.object(obj, '_convert_audio', side_effect=convert):
                    ok, msg = obj._pipeline_download_and_convert(BASE, directory, 'mp3', 'generic', mode, limit, 2)
                self.assertTrue(ok, msg)
                self.assertEqual(seen, [str(n) for n in range(count)])
                self.assertEqual(len(list(Path(directory).rglob('*.mp3'))), count)
                self.assertFalse(list(Path(directory).rglob('*.klmp3-source')))
                if mode == DL_MODE_PLAYLIST:
                    self.assertTrue((Path(directory) / 'Série' / '01 - 0.mp3').exists())


if __name__ == '__main__':
    unittest.main()
