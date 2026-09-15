"""Podcasts web: structured audio, HTML audio and RSS, with no browser execution."""
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class PodcastError(ValueError):
    pass


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; KLMP3)', 'Accept': 'text/html, application/rss+xml, application/xml'})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise PodcastError('Podcasts web : page ou flux trop volumineux.')
        return body.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')


def http_url(value, base):
    if not isinstance(value, str) or not value.strip():
        return None
    url = urllib.parse.urljoin(base, value)
    return url if urllib.parse.urlsplit(url).scheme in ('http', 'https') else None


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.scripts, self.audio, self.feeds = [], [], []
        self.title = ''
        self.script = None
        self.in_title = self.in_audio = False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script' and a.get('type') in ('application/ld+json', 'application/json'):
            self.script = [a, '']
        if tag == 'title':
            self.in_title = True
        if tag == 'audio':
            self.in_audio = True
        if tag == 'audio' or (tag == 'source' and self.in_audio):
            if a.get('src'):
                self.audio.append(a['src'])
        if tag in ('a', 'link') and a.get('href'):
            # Never follow a general /rss directory or unrelated navigation.
            if a.get('type') == 'application/rss+xml' or a['href'].split('?')[0].endswith(('.rss', '/rss.xml')):
                self.feeds.append(a['href'])

    def handle_data(self, data):
        if self.script is not None:
            self.script[1] += data
        if self.in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.scripts.append(self.script)
            self.script = None
        if tag == 'title':
            self.in_title = False
        if tag == 'audio':
            self.in_audio = False


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def nuxt_records(table):
    """Read the indexed JSON records used by Nuxt, without executing JavaScript.

    Resolve each record separately with a depth cap: Nuxt state may be cyclic.
    Unknown reducer types need not be evaluated to extract plain audio records.
    """
    def expand(value, depth=0):
        if depth > 12:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            if value < 0 or value >= len(table):
                return None
            item = table[value]
            if isinstance(item, dict):
                return {k: expand(v, depth + 1) for k, v in item.items()}
            if isinstance(item, list):
                return [expand(v, depth + 1) for v in item]
            return item
        return value
    for item in table:
        if isinstance(item, dict) and 'audio_url' in item:
            yield {k: expand(v) for k, v in item.items()}


def audio_info(record, base, title='Podcast'):
    url = http_url(record.get('audio_url') or record.get('contentUrl'), base)
    if not url:
        return None
    ext = urllib.parse.urlsplit(url).path.rsplit('.', 1)[-1].lower()
    if ext not in ('mp3', 'm4a', 'aac', 'ogg', 'opus', 'wav', 'flac'):
        mime = record.get('encodingFormat', '')
        ext = {'audio/mp4': 'm4a', 'audio/mpeg': 'mp3'}.get(mime)
    if ext not in ('mp3', 'm4a', 'aac', 'ogg', 'opus', 'wav', 'flac'):
        return None
    authors = record.get('authors') or record.get('author') or []
    if not isinstance(authors, list):
        authors = [authors]
    author = ', '.join(str(a.get('name') or a.get('title') or '') if isinstance(a, dict) else str(a) for a in authors)
    from yt_dlp.utils import parse_duration
    return {'duration': parse_duration(record.get('duration') or (record.get('attributes') or {}).get('duration')),
            'track': record.get('title') or record.get('name') or title,
            'id': str(record.get('slug') or hashlib.sha256(url.encode()).hexdigest()[:16]),
            'title': record.get('title') or record.get('name') or title,
            'url': url, 'ext': ext, 'vcodec': 'none', 'webpage_url': base,
            'extractor': 'web_podcast', 'artist': author or None,
            'thumbnail': http_url(record.get('thumbnailUrl') or record.get('thumb_list_url'), base),
            'release_date': re.sub(r'\D', '', str(record.get('published_at') or record.get('datePublished') or ''))[:8] or None,
            'http_headers': {'Referer': base}}


def rss_info(source, url):
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise PodcastError('Podcasts web : flux RSS invalide.') from exc
    channel = root.find('channel')
    if channel is None:
        raise PodcastError('Podcasts web : flux RSS sans chaîne.')
    title = channel.findtext('title') or 'Podcast'
    entries = []
    for item in channel.findall('item'):
        enclosure = item.find('enclosure')
        if enclosure is None:
            continue
        info = audio_info({'contentUrl': enclosure.get('url'), 'encodingFormat': enclosure.get('type'), 'title': item.findtext('title')}, url)
        if info:
            from yt_dlp.utils import parse_duration
            info['duration'] = parse_duration(item.findtext('{http://www.itunes.com/dtds/podcast-1.0.dtd}duration'))
            try:
                info['release_date'] = parsedate_to_datetime(item.findtext('pubDate')).strftime('%Y%m%d')
            except (TypeError, ValueError, AttributeError):
                pass
            info['album'] = title
            info['thumbnail'] = channel.findtext('image/url')
            info['artist'] = item.findtext('{http://www.itunes.com/dtds/podcast-1.0.dtd}author')
            entries.append(info)
    if not entries:
        raise PodcastError('Podcasts web : aucun épisode audio dans le flux RSS.')
    return {'title': title, 'entries': entries}


def resolve(url, log=lambda message: None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    blast = parsed.hostname in ('www.blast-info.fr', 'blast-info.fr', 'api.blast-info.fr')
    try:
        source = fetch(url)
    except (OSError, ValueError) as exc:
        if blast:
            raise PodcastError('Podcasts web : impossible de charger cette page ou ce flux.') from exc
        return None
    if re.match(r'\s*(?:<\?xml[^>]*>\s*)?<rss\b', source):
        return rss_info(source, url)
    page = Page(source)
    entries, structured = [], []
    for attrs, text in page.scripts:
        try:
            data = json.loads(text)
        except (ValueError, RecursionError):
            continue
        records = nuxt_records(data) if attrs.get('id') == '__NUXT_DATA__' and isinstance(data, list) else walk(data)
        for record in records:
            entity = record.get('mainEntity')
            if isinstance(entity, dict) and entity.get('@type') == 'AudioObject':
                enriched = dict(entity)
                enriched.setdefault('name', record.get('headline') or record.get('name') or page.title)
                enriched.setdefault('author', record.get('author'))
                enriched.setdefault('datePublished', record.get('datePublished') or record.get('dateCreated'))
                image = record.get('image')
                if isinstance(image, dict):
                    image = image.get('url')
                if isinstance(image, str):
                    enriched.setdefault('thumbnailUrl', image)
                info = audio_info(enriched, url, page.title)
                if info:
                    structured.append(info)
            types = record.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if 'audio_url' in record:
                info = audio_info(record, url, page.title)
                if info:
                    entries.append(info)
            elif 'AudioObject' in types:
                info = audio_info(record, url, page.title)
                if info:
                    structured.append(info)
    if structured:
        # JSON-LD describes this page's media, before recommendations/state.
        return structured[0]
    # An episode URL must select that episode, never the first recommendation.
    slug = parsed.path.rstrip('/').rsplit('/', 1)[-1]
    selected = next((e for e in entries if e['id'] == slug), None)
    if selected:
        return selected
    is_blast_episode = blast and len(parsed.path.strip('/').split('/')) >= 3 and not parsed.path.endswith('rss.xml')
    if is_blast_episode:
        raise PodcastError('Podcasts web : aucun audio disponible pour cet épisode.')
    for src in page.audio:
        info = audio_info({'contentUrl': src}, url, page.title)
        if info:
            return info
    # Follow only an unambiguous feed. Multiple feeds require user selection.
    feeds = list(dict.fromkeys(http_url(f, url) for f in page.feeds))
    matching_feeds = [f for f in feeds if f and slug in urllib.parse.urlsplit(f).path.split('/')]
    if matching_feeds:
        feeds = matching_feeds
    if len(feeds) == 1 and feeds[0]:
        try:
            result = rss_info(fetch(feeds[0]), feeds[0])
            if entries:
                # Preserve the page order, even if the RSS is newest-first.
                order = {e['url']: n for n, e in enumerate(entries)}
                result['entries'].sort(key=lambda e: order.get(e['url'], len(order)))
            return result
        except (OSError, ValueError):
            log('Flux RSS indisponible ; recherche des audios dans la page.')
    if entries:
        unique = {e['url']: e for e in reversed(entries)}
        entries = list(reversed(list(unique.values())))
        return {'title': page.title.strip() or 'Podcast', 'entries': entries}
    if blast:
        raise PodcastError('Podcasts web : aucun audio trouvé sur cette page.')
    return None
