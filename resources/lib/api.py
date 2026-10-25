# -*- coding: utf-8 -*-
"""PBS Kids web API client.

Pure Python (no Kodi imports) so it can be unit tested outside Kodi.
All endpoint knowledge lives here: if PBS changes its API, this is the
only file that should need updating.
"""
import hashlib
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HOME_URL = 'https://content.services.pbskids.org/v2/kidspbsorg/home/'
VIDEOS_URL = 'https://producerplayer.services.pbskids.org/show-list/'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

SHOW_IMAGE_KEYS = ('mezzanine_16x9', 'program-kids-square', 'logo', 'background')
VIDEO_IMAGE_KEYS = ('kids-mezzannine-16x9', 'mezzanine_16x9', 'kids-mezzannine-4x3')


class PBSKidsAPI(object):

    def __init__(self, cache_dir=None, cache_hours=6, fetch=None):
        self.cache_dir = cache_dir
        self.cache_seconds = cache_hours * 3600
        self._fetch = fetch or self._http_get

    # ---------------------------------------------------------------- HTTP

    @staticmethod
    def _http_get(url):
        req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode('utf-8')

    def get_json(self, url, use_cache=True):
        path = None
        if use_cache and self.cache_dir and self.cache_seconds > 0:
            path = os.path.join(self.cache_dir, hashlib.md5(url.encode('utf-8')).hexdigest() + '.json')
            if os.path.exists(path) and time.time() - os.path.getmtime(path) < self.cache_seconds:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        text = self._fetch(url).strip()
        # Some PBS endpoints answer JSONP: callback({...})
        if text and text[0] not in '{[':
            text = text[text.find('(') + 1:text.rfind(')')]
        data = json.loads(text)
        if path:
            if not os.path.isdir(self.cache_dir):
                os.makedirs(self.cache_dir)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        return data

    def clear_cache(self):
        if self.cache_dir and os.path.isdir(self.cache_dir):
            for name in os.listdir(self.cache_dir):
                if name.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, name))

    # --------------------------------------------------------------- Shows

    def get_shows(self):
        """Return a list of show dicts sorted A-Z: slug, title, plot, image, age."""
        data = self.get_json(HOME_URL)
        shows = {}
        for node in _walk(data):
            slug = node.get('slug')
            title = node.get('title')
            if not slug or not title or not isinstance(slug, str):
                continue
            # Show objects carry images/description; skip videos and collections
            if 'images' not in node or node.get('nola_episode') or node.get('mp4'):
                continue
            show = shows.setdefault(slug, {'slug': slug, 'title': title, 'plot': '', 'image': '', 'age': ''})
            # The same show can appear in several collections; keep the richest data
            show['plot'] = show['plot'] or node.get('description') or node.get('description_short') or ''
            show['image'] = show['image'] or _pick_image(node.get('images'), SHOW_IMAGE_KEYS)
            show['age'] = show['age'] or node.get('age_range') or ''
        return sorted(shows.values(), key=lambda s: s['title'].lower())

    def search_shows(self, query):
        q = query.lower().strip()
        return [s for s in self.get_shows() if q in s['title'].lower() or q in s['plot'].lower()]

    # -------------------------------------------------------------- Videos

    def get_videos(self, slug, video_type='episode', page=1, page_size=30):
        """Return (videos, has_more) for one show."""
        params = {
            'shows': slug,
            'available': 'public',
            'sort': '-encored_on',
            'type': video_type,
            'page': page,
            'page_size': page_size,
        }
        data = self.get_json('%s?%s' % (VIDEOS_URL, urlencode(params)))
        if not isinstance(data, dict):
            return [], False
        items = data.get('items') or []
        videos = [v for v in (_parse_video(i) for i in items) if v['url']]
        if 'next' in data:
            has_more = bool(data['next'])
        else:
            total = (data.get('meta') or {}).get('count') or data.get('count') or 0
            has_more = total > page * page_size if total else len(items) >= page_size
        return videos, has_more


# ------------------------------------------------------------------ helpers

def _walk(node):
    """Yield every dict inside a nested JSON structure."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _pick_image(images, preferred):
    if isinstance(images, dict):
        for key in preferred:
            img = images.get(key)
            url = img.get('url') if isinstance(img, dict) else img
            if url:
                return url
        for img in images.values():
            url = img.get('url') if isinstance(img, dict) else img
            if isinstance(url, str) and url.startswith('http'):
                return url
    if isinstance(images, list):
        for img in images:
            url = img.get('url') if isinstance(img, dict) else None
            if url:
                return url
    return ''


def _pick_stream(item):
    """Prefer HLS (adaptive), then the highest bitrate MP4."""
    videos = item.get('videos') or []
    if isinstance(videos, dict):
        videos = [dict(v, profile=k) if isinstance(v, dict) else {'profile': k, 'url': v}
                  for k, v in videos.items()]
    hls = [v for v in videos if isinstance(v, dict) and 'hls' in str(v.get('profile', '')).lower() and v.get('url')]
    if hls:
        return hls[0]['url']
    mp4 = [v for v in videos if isinstance(v, dict) and v.get('url')]
    if mp4:
        mp4.sort(key=lambda v: v.get('bitrate') or _digits(v.get('profile')), reverse=True)
        return mp4[0]['url']
    return item.get('mp4') or item.get('URI') or ''


def _pick_captions(item):
    caps = item.get('closedCaptions') or item.get('captions') or []
    if isinstance(caps, dict):
        caps = [dict(v, format=k) if isinstance(v, dict) else {'format': k, 'URI': v} for k, v in caps.items()]
    ranked = sorted((c for c in caps if isinstance(c, dict)),
                    key=lambda c: ('srt', 'webvtt', 'vtt').index(str(c.get('format', '')).lower())
                    if str(c.get('format', '')).lower() in ('srt', 'webvtt', 'vtt') else 9)
    for c in ranked:
        url = c.get('URI') or c.get('url')
        if url:
            return url
    return ''


def _digits(text):
    num = ''.join(ch for ch in str(text or '') if ch.isdigit())
    return int(num) if num else 0


def _parse_video(item):
    program = item.get('program') or {}
    duration = item.get('duration') or 0
    try:
        duration = int(float(duration))
    except (TypeError, ValueError):
        duration = 0
    return {
        'title': item.get('title') or '',
        'plot': item.get('description') or item.get('description_long') or '',
        'image': _pick_image(item.get('images'), VIDEO_IMAGE_KEYS),
        'url': _pick_stream(item),
        'captions': _pick_captions(item),
        'duration': duration,
        'aired': (item.get('air_date') or item.get('encored_on') or '')[:10],
        'show': program.get('title') if isinstance(program, dict) else '',
    }
