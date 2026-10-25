# -*- coding: utf-8 -*-
"""Offline tests: run with  python3 -m unittest discover tests"""
import json
import os
import sys
import tempfile
import unittest
from urllib.parse import parse_qsl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'fakekodi'))
sys.path.insert(0, os.path.dirname(HERE))

import xbmc  # noqa: E402
import xbmcgui  # noqa: E402
import xbmcplugin  # noqa: E402
from resources.lib import api, router  # noqa: E402
from resources.lib.storage import Favourites, SearchHistory  # noqa: E402

HOME = {
    'collections': {
        'spotlight': {'content': [
            {'slug': 'daniel-tigers-neighborhood', 'title': "Daniel Tiger's Neighborhood",
             'description': 'Feelings and friends.', 'age_range': '2-4',
             'images': {'mezzanine_16x9': {'url': 'https://img/daniel.jpg'}}},
            {'slug': 'wild-kratts', 'title': 'Wild Kratts', 'description': 'Animal adventures.',
             'images': {'logo': 'https://img/wk.png'}},
        ]},
        'videos': {'content': [
            {'slug': 'some-video', 'title': 'A video', 'mp4': 'https://v.mp4', 'images': {}},
        ]},
        'dupe': {'content': [
            {'slug': 'wild-kratts', 'title': 'Wild Kratts', 'images': {}},
        ]},
    }
}

VIDEOS = {
    'items': [
        {'title': 'Daniel Goes to School', 'description': 'First day.', 'duration': '1560',
         'air_date': '2024-09-02T00:00:00',
         'images': {'kids-mezzannine-16x9': {'url': 'https://img/ep1.jpg'}},
         'videos': [{'profile': 'mp4-1200k', 'url': 'https://v/1200.mp4', 'bitrate': 1200},
                    {'profile': 'hls-16x9-1080p', 'url': 'https://v/ep1.m3u8'}],
         'closedCaptions': [{'format': 'DFXP', 'URI': 'https://c/ep1.dfxp'},
                            {'format': 'SRT', 'URI': 'https://c/ep1.srt'}],
         'program': {'title': "Daniel Tiger's Neighborhood"}},
        {'title': 'Clip with mp4 dict', 'videos': {'mp4-800k': {'url': 'https://v/800.mp4'},
                                                     'mp4-2500k': {'url': 'https://v/2500.mp4'}}},
        {'title': 'No stream'},
    ],
    'meta': {'count': 5},
}


def fake_fetch(url):
    if url.startswith(api.HOME_URL):
        return json.dumps(HOME)
    if url.startswith(api.VIDEOS_URL):
        return 'cb(%s)' % json.dumps(VIDEOS)  # JSONP on purpose
    raise IOError('offline')


class ApiTests(unittest.TestCase):

    def setUp(self):
        self.api = api.PBSKidsAPI(fetch=fake_fetch, cache_hours=0)

    def test_shows_sorted_unique_and_filtered(self):
        shows = self.api.get_shows()
        self.assertEqual([s['slug'] for s in shows], ['daniel-tigers-neighborhood', 'wild-kratts'])
        self.assertEqual(shows[0]['image'], 'https://img/daniel.jpg')
        self.assertEqual(shows[0]['age'], '2-4')
        self.assertEqual(shows[1]['image'], 'https://img/wk.png')

    def test_search(self):
        self.assertEqual([s['slug'] for s in self.api.search_shows('ANIMAL')], ['wild-kratts'])

    def test_videos(self):
        videos, more = self.api.get_videos('daniel-tigers-neighborhood', page=1, page_size=2)
        self.assertEqual(len(videos), 2)
        self.assertTrue(more)
        ep = videos[0]
        self.assertEqual(ep['url'], 'https://v/ep1.m3u8')
        self.assertEqual(ep['captions'], 'https://c/ep1.srt')
        self.assertEqual(ep['duration'], 1560)
        self.assertEqual(ep['aired'], '2024-09-02')
        self.assertEqual(videos[1]['url'], 'https://v/2500.mp4')
        _, more = self.api.get_videos('x', page=3, page_size=2)
        self.assertFalse(more)

    def test_cache(self):
        calls = []
        tmp = tempfile.mkdtemp()
        cached = api.PBSKidsAPI(cache_dir=tmp, cache_hours=1,
                                fetch=lambda u: calls.append(u) or fake_fetch(u))
        cached.get_shows()
        cached.get_shows()
        self.assertEqual(len(calls), 1)
        cached.clear_cache()
        cached.get_shows()
        self.assertEqual(len(calls), 2)


class StorageTests(unittest.TestCase):

    def test_favourites(self):
        fav = Favourites(os.path.join(tempfile.mkdtemp(), 'sub', 'f.json'))
        fav.add({'slug': 'a', 'title': 'A'})
        fav.add({'slug': 'b', 'title': 'B'})
        fav.add({'slug': 'a', 'title': 'A'})
        self.assertEqual([s['slug'] for s in fav.load()], ['a', 'b'])
        fav.remove('a')
        self.assertFalse(fav.contains('a'))

    def test_history(self):
        hist = SearchHistory(os.path.join(tempfile.mkdtemp(), 'h.json'), limit=2)
        for term in ('cat', 'dog', 'Cat', 'fish'):
            hist.add(term)
        self.assertEqual(hist.load(), ['fish', 'Cat'])
        hist.clear()
        self.assertEqual(hist.load(), [])


class RouterTests(unittest.TestCase):

    def setUp(self):
        xbmcplugin.reset()
        api.PBSKidsAPI._http_get = staticmethod(fake_fetch)

    def run_plugin(self, query=''):
        router.run(['plugin://plugin.video.pbskids/', '1', '?' + query])
        return list(xbmcplugin.items)

    def follow(self, url):
        return self.run_plugin(url.split('?', 1)[1])

    def test_full_browse_and_play(self):
        root = self.run_plugin()
        self.assertEqual([li.label for _, li, _ in root], ['S30000', 'S30001', 'S30002'])
        shows = self.follow(root[0][0])[3:]
        self.assertEqual(shows[0][1].label, "Daniel Tiger's Neighborhood")
        xbmcplugin.reset()
        sections = self.follow(shows[0][0])
        xbmcplugin.reset()
        episodes = self.follow(sections[0][0])
        self.assertEqual(episodes[-1][1].label, 'S30007 (2)')
        self.assertEqual(episodes[0][1].props['IsPlayable'], 'true')
        xbmcplugin.reset()
        self.follow(episodes[0][0])
        played = xbmcplugin.resolved[0]
        self.assertEqual(played.path, 'https://v/ep1.m3u8')
        self.assertEqual(played.mime, 'application/vnd.apple.mpegurl')
        self.assertEqual(played.subtitles, ['https://c/ep1.srt'])

    def test_favourite_round_trip(self):
        shows = self.run_plugin('action=shows')
        add_cmd = shows[0][1].menu[0][1]
        self.follow(add_cmd[len('RunPlugin('):-1])
        xbmcplugin.reset()
        favs = self.run_plugin('action=favourites')
        self.assertEqual(len(favs), 1)
        self.assertEqual(favs[0][1].menu[0][0], 'S30009')

    def test_search_flow(self):
        xbmcgui.input_value = 'kratts'
        results = self.run_plugin('action=new_search')
        self.assertEqual([li.label for _, li, _ in results], ['Wild Kratts'])
        xbmcplugin.reset()
        menu = self.run_plugin('action=search')
        self.assertIn('kratts', [li.label for _, li, _ in menu])
        params = dict(parse_qsl(menu[1][0].split('?', 1)[1]))
        self.assertEqual(params, {'action': 'search_results', 'query': 'kratts'})

    def test_network_error_is_reported(self):
        api.PBSKidsAPI._http_get = staticmethod(lambda url: (_ for _ in ()).throw(IOError('down')))
        self.run_plugin('action=shows')
        self.assertEqual(xbmcplugin.ended, [False])
        self.assertEqual(xbmcgui.notifications[-1][1], 'S30012')


if __name__ == '__main__':
    unittest.main()
