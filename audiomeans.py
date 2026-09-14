"""Audiomeans player discovery and metadata, without caching signed media URLs.

player-v2 embeds JSON in window.__INITIAL_DATA__. episode.audio.path is
requested by the player; the audio server redirects to a freshly signed file.
"""
import html
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request


class AudiomeansError(ValueError):
    pass


HOSTS = {"podcasts.audiomeans.fr", "files.audiomeans.fr", "audio.audiomeans.fr"}
PLAYER_PATH = re.compile(r"^/player-v2/([^/]+)/episodes/([0-9a-fA-F-]{36})/?$")


def is_audiomeans(url):
    return urllib.parse.urlsplit(url).hostname in HOSTS


def find_player(page):
    # Unwrap Embedly before scanning the whole document, so its own query
    # parameters cannot become part of the nested player's URL.
    for attribute in re.findall(r"(?:src|href|data-src)=[\"']([^\"']+)", page):
        wrapper = urllib.parse.urlsplit(html.unescape(attribute))
        if wrapper.hostname != "cdn.embedly.com":
            continue
        query = urllib.parse.parse_qs(wrapper.query)
        for key in ("src", "url"):
            for value in query.get(key, []):
                nested = urllib.parse.urlsplit(value)
                if nested.hostname == "podcasts.audiomeans.fr" and PLAYER_PATH.fullmatch(nested.path):
                    return "https:" + value if value.startswith("//") else value
    # Embedly query strings can encode the URL several times. Decode only
    # for discovery, never decode a media URL or its signature.
    for _ in range(4):
        page = html.unescape(page).replace(r"\/", "/")
        for candidate in re.findall(r'(?:https?:)?//podcasts\.audiomeans\.fr/player-v2/[^\s<>"\'\\]+', page):
            candidate = "https:" + candidate if candidate.startswith("//") else candidate
            if "?" not in candidate:
                candidate = candidate.split("&", 1)[0]
            parsed = urllib.parse.urlsplit(candidate)
            if PLAYER_PATH.fullmatch(parsed.path):
                return candidate
        decoded = urllib.parse.unquote(page)
        if decoded == page:
            break
        page = decoded
    return None


def _read_html(url, cookie_jar=None, referer=None):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; KLMP3)",
        "Accept": "text/html", "Cache-Control": "no-cache",
    })
    if referer:
        request.add_header("Referer", referer)
    open_url = (urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar)).open
                if cookie_jar is not None else urllib.request.urlopen)
    with open_url(request, timeout=20) as response:
        if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
            return ""
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise AudiomeansError("Page trop volumineuse pour rechercher le lecteur Audiomeans.")
        return body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def player_info(page, player_url):
    match = re.search(r"window\.__INITIAL_DATA__\s*=\s*", page)
    try:
        if not match:
            raise ValueError()
        data, _ = json.JSONDecoder().raw_decode(page[match.end():])
        episode = data["episode"]
        requested = PLAYER_PATH.fullmatch(urllib.parse.urlsplit(player_url).path)
        if not requested or episode["id"].lower() != requested[2].lower():
            raise ValueError()
        if episode.get("audio") is None:
            raise AudiomeansError(
                "Audiomeans reconnaît cet épisode, mais ne fournit aucun audio à KLMP3 "
                "(audio absent dans les données du lecteur). Vérifiez si la lecture "
                "démarre réellement dans Firefox sur cette même page."
            )
        audio_url = episode["audio"]["path"]
        parsed = urllib.parse.urlsplit(audio_url)
        if parsed.scheme not in ("https", "http") or parsed.hostname not in HOSTS - {"podcasts.audiomeans.fr"}:
            raise ValueError()
        if (episode.get("adsSignature") or {}).get("hm"):
            audio_url = "https://player.audiomeans.fr/player-v2/mp3/" + audio_url.split("://", 1)[1]
        podcast = data.get("podcast") or {}
        return {
            "id": episode["id"], "title": episode.get("title") or episode["id"],
            "url": audio_url, "ext": "mp3", "vcodec": "none", "acodec": "mp3",
            "extractor": "audiomeans", "webpage_url": player_url,
            "album": podcast.get("name"), "artist": podcast.get("authorName"),
            "thumbnail": episode.get("imageUrl") or podcast.get("imageUrl"),
        }
    except AudiomeansError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise AudiomeansError("Audiomeans : épisode introuvable, audio indisponible ou lecteur non reconnu.") from exc


def _is_mediapart(host):
    return host == "mediapart.fr" or bool(host and host.endswith(".mediapart.fr"))


def _firefox_mediapart_cookies():
    # Keep only the site's cookies in memory; CookieJar applies domain/path/
    # secure rules on requests and redirects. Never copy a raw Cookie header.
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
        cookies = extract_cookies_from_browser("firefox")
        scoped = http.cookiejar.CookieJar()
        for cookie in cookies:
            if _is_mediapart(cookie.domain.lstrip(".")):
                scoped.set_cookie(cookie)
        if not list(scoped):
            raise ValueError("No Mediapart cookies")
        return scoped
    except Exception as exc:
        raise AudiomeansError(
            "Session Firefox Mediapart indisponible. Connectez-vous à Mediapart "
            "dans le profil Firefox par défaut, puis réessayez. "
            "La lecture de session nécessite le module Python yt-dlp."
        ) from exc


def resolve(url, log=lambda message: None):
    """Return yt-dlp info, or None to retain the existing generic extraction.

    Direct files are accepted as supplied; an expired signed URL cannot be
    renewed without its original player. No URL or metadata cache is written.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        return None
    direct = is_audiomeans(url)
    if parsed.hostname in ("files.audiomeans.fr", "audio.audiomeans.fr"):
        name = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]).rsplit(".", 1)[0] or "audio"
        return {"id": name, "title": name, "url": url, "ext": "mp3", "vcodec": "none", "acodec": "mp3", "extractor": "audiomeans"}
    if direct and not PLAYER_PATH.fullmatch(parsed.path):
        raise AudiomeansError("Audiomeans : URL de lecteur invalide ; utilisez player-v2/<podcast>/episodes/<identifiant>.")
    page = ""
    page_error = None
    try:
        page = _read_html(url)
    except (OSError, ValueError) as exc:
        page_error = exc
        if direct:
            raise AudiomeansError("Audiomeans : impossible de charger le lecteur (accès refusé, épisode absent ou erreur réseau).") from exc
    player_url = url if direct else find_player(page)
    if not player_url and _is_mediapart(parsed.hostname):
        log("🍪 Lecteur absent de la page publique : tentative avec la session Firefox Mediapart…")
        cookies = _firefox_mediapart_cookies()
        try:
            page = _read_html(url, cookie_jar=cookies)
        except (OSError, ValueError) as exc:
            raise AudiomeansError("Impossible de consulter la page Mediapart avec la session Firefox.") from exc
        player_url = find_player(page)
        if not player_url:
            raise AudiomeansError(
                "Aucun lecteur Audiomeans trouvé après connexion via Firefox. "
                "Vérifiez que ce profil Firefox permet de lire cet article avec votre abonnement. "
                "Le lecteur peut aussi être chargé uniquement par JavaScript."
            )
    elif page_error:
        log("Recherche Audiomeans impossible sur cette page ; tentative avec yt-dlp.")
        return None
    if not player_url:
        log("Aucun lecteur Audiomeans détecté ; tentative avec yt-dlp.")
        return None
    if not direct:
        try:
            page = _read_html(player_url, referer=url)
        except (OSError, ValueError) as exc:
            raise AudiomeansError("Audiomeans : impossible de charger le lecteur intégré.") from exc
    log("🎯 Lecteur Audiomeans détecté : récupération des métadonnées actuelles.")
    info = player_info(page, player_url)
    if not direct:
        info["http_headers"] = {"Referer": url}
    return info
