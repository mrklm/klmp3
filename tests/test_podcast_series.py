import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klmp3 import DL_MODE_SINGLE, DL_MODE_PLAYLIST
from test_audiomeans import harness
import web_podcast as web

URL = 'https://example.org/series/safety'


def source(items=None, extra=''):
    if items is None:
        items = [{'position': 2, 'url': '/episodes/two'}, {'position': 1, 'url': '/episodes/one'}]
    data = {'@graph': [
        {'@type': 'WebPage', 'url': URL, 'name': 'Safety', 'mainEntity': {'@type': 'PodcastSeries'}},
        {'@type': 'ItemList', 'itemListElement': items},
        {'@type': 'BreadcrumbList', 'itemListElement': [{'url': '/unrelated'}]},
    ]}
    return '<script type="application/ld+json">' + json.dumps(data) + '</script><a href="/recommendation">Other</a>' + extra


class SeriesTests(unittest.TestCase):
    def test_generic_order_without_crawling_episode_pages(self):
        with patch.object(web, 'fetch', return_value=source()) as fetch:
            info = web.resolve(URL)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual([e['episode_url'] for e in info['entries']], ['https://example.org/episodes/one', 'https://example.org/episodes/two'])

    def test_requires_podcast_series(self):
        with patch.object(web, 'fetch', return_value=source().replace('PodcastSeries', 'WebSite')):
            self.assertIsNone(web.resolve(URL))

    def test_duplicates_removed(self):
        items = [{'url': '/episodes/one'}, {'url': '/episodes/one'}]
        self.assertEqual(len(web.series_info(web.Page(source(items)), URL)['entries']), 1)

    def test_foreign_link_rejected(self):
        with self.assertRaises(web.PodcastError):
            web.series_info(web.Page(source([{'url': 'https://other.org/episode'}])), URL)

    def test_pagination_not_silently_truncated(self):
        with patch.object(web, 'fetch', return_value=source(extra='<script>pagination:{lastPage:2}</script>')):
            with self.assertRaisesRegex(web.PodcastError, 'plusieurs pages'):
                web.resolve(URL)

    def test_selected_references_only_are_resolved(self):
        for mode, limited, expected in [(DL_MODE_SINGLE, False, 1), (DL_MODE_PLAYLIST, True, 1), (DL_MODE_PLAYLIST, False, 2)]:
            with self.subTest(mode=mode, limited=limited), tempfile.TemporaryDirectory() as folder:
                app = harness()
                series = web.series_info(web.Page(source()), URL)
                visited = []
                def resolve(url, log):
                    if url == URL:
                        return series
                    visited.append(url)
                    return web.audio_info({'contentUrl': url + '.mp3', 'title': url.rsplit('/', 1)[-1]}, url)
                def download(url, template, *args, **kwargs):
                    info = kwargs['audio_info']
                    self.assertEqual(info['album'], 'Safety')
                    path = Path(template).parent / (info['title'] + '.mp3')
                    path.write_bytes(b'fixture')
                    return True, str(path)
                def convert(path, fmt):
                    target = Path(path).with_suffix('.mp3')
                    target.write_bytes(b'converted')
                    return True, str(target)
                with patch('klmp3.resolve_audiomeans', return_value=None), patch('klmp3.resolve_web_podcast', side_effect=resolve), patch.object(app, '_download_audio', side_effect=download), patch.object(app, '_convert_audio', side_effect=convert):
                    ok, message = app._pipeline_download_and_convert(URL, folder, 'mp3', 'generic', mode, limited, 1)
                self.assertTrue(ok, message)
                if expected == 1:
                    self.assertTrue((Path(folder) / 'one.mp3').is_file())
                    self.assertFalse((Path(folder) / 'Safety').exists())
                else:
                    self.assertTrue((Path(folder) / 'Safety' / '01 - one.mp3').is_file())
                    self.assertTrue((Path(folder) / 'Safety' / '02 - two.mp3').is_file())
                self.assertEqual(visited, [e['episode_url'] for e in series['entries'][:expected]])

    def test_failed_episode_is_not_silently_skipped(self):
        app = harness()
        series = web.series_info(web.Page(source()), URL)
        with tempfile.TemporaryDirectory() as folder, patch('klmp3.resolve_audiomeans', return_value=None), patch('klmp3.resolve_web_podcast', side_effect=[series, None]), patch.object(app, '_download_audio') as download:
            ok, message = app._pipeline_download_and_convert(URL, folder, 'mp3', 'generic', DL_MODE_SINGLE, False, 0)
        self.assertFalse(ok)
        self.assertIn('épisode 1', message)
        download.assert_not_called()
