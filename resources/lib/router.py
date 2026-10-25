# -*- coding: utf-8 -*-
"""Kodi routing and directory building."""
import json
import os
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.api import PBSKidsAPI
from resources.lib.storage import Favourites, SearchHistory

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ICON = ADDON.getAddonInfo('icon')
FANART = ADDON.getAddonInfo('fanart')
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))


def _(string_id):
    return ADDON.getLocalizedString(string_id)


def _int_setting(key, default):
    try:
        return int(ADDON.getSetting(key))
    except ValueError:
        return default


class Router(object):

    def __init__(self, argv):
        self.base = argv[0]
        self.handle = int(argv[1])
        self.params = dict(parse_qsl(argv[2].lstrip('?')))
        self.api = PBSKidsAPI(cache_dir=os.path.join(PROFILE, 'cache'),
                              cache_hours=_int_setting('cache_hours', 6))
        self.favourites = Favourites(os.path.join(PROFILE, 'favourites.json'))
        self.history = SearchHistory(os.path.join(PROFILE, 'search_history.json'), limit=50)
        self.page_size = _int_setting('page_size', 30)

    def url(self, **kwargs):
        return '%s?%s' % (self.base, urlencode(kwargs))

    # ------------------------------------------------------------ dispatch

    def dispatch(self):
        action = self.params.get('action', 'root')
        handler = getattr(self, 'do_' + action, None)
        if handler is None:
            xbmc.log('[%s] unknown action %s' % (ADDON_ID, action), xbmc.LOGWARNING)
            return
        try:
            handler()
        except (IOError, ValueError) as e:
            xbmc.log('[%s] network error: %s' % (ADDON_ID, e), xbmc.LOGERROR)
            xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), _(30012), xbmcgui.NOTIFICATION_ERROR)
            if self.handle >= 0 and action not in ('play',):
                xbmcplugin.endOfDirectory(self.handle, succeeded=False)

    # --------------------------------------------------------------- menus

    def do_root(self):
        self.add_folder(_(30000), self.url(action='shows'), 'DefaultTVShows.png')
        self.add_folder(_(30001), self.url(action='favourites'), 'DefaultFavourites.png')
        self.add_folder(_(30002), self.url(action='search'), 'DefaultAddonsSearch.png')
        self.end()

    def do_shows(self):
        self.list_shows(self.api.get_shows())

    def do_favourites(self):
        self.list_shows(self.favourites.load())

    def do_show(self):
        slug, title = self.params['slug'], self.params.get('title', '')
        self.add_folder(_(30005), self.url(action='videos', slug=slug, title=title, type='episode', page=1),
                        'DefaultTVShows.png')
        self.add_folder(_(30006), self.url(action='videos', slug=slug, title=title, type='clip', page=1),
                        'DefaultMovies.png')
        self.end()

    def do_videos(self):
        slug = self.params['slug']
        title = self.params.get('title', '')
        vtype = self.params.get('type', 'episode')
        page = int(self.params.get('page', 1))
        videos, has_more = self.api.get_videos(slug, vtype, page, self.page_size)
        subtitles = ADDON.getSetting('subtitles') != 'false'
        for v in videos:
            li = xbmcgui.ListItem(v['title'], offscreen=True)
            li.setArt({'thumb': v['image'] or ICON, 'icon': v['image'] or ICON,
                       'fanart': v['image'] or FANART})
            _set_info(li, {'title': v['title'], 'plot': v['plot'], 'duration': v['duration'],
                           'aired': v['aired'], 'tvshowtitle': v['show'] or title,
                           'mediatype': 'episode' if vtype == 'episode' else 'video'})
            li.setProperty('IsPlayable', 'true')
            play_url = self.url(action='play', url=v['url'],
                                captions=v['captions'] if subtitles else '')
            xbmcplugin.addDirectoryItem(self.handle, play_url, li, isFolder=False)
        if has_more:
            self.add_folder('%s (%d)' % (_(30007), page + 1),
                            self.url(action='videos', slug=slug, title=title, type=vtype, page=page + 1),
                            'DefaultFolder.png')
        if not videos and page == 1:
            xbmcgui.Dialog().notification(title or ADDON.getAddonInfo('name'), _(30011), ICON)
        xbmcplugin.setContent(self.handle, 'episodes')
        self.end(cache=False)

    # -------------------------------------------------------------- search

    def do_search(self):
        self.add_folder('[B]%s[/B]' % _(30003), self.url(action='new_search'), 'DefaultAddonsSearch.png')
        terms = self.history.load()
        for term in terms:
            li = xbmcgui.ListItem(term)
            li.setArt({'icon': 'DefaultAddonsSearch.png', 'fanart': FANART})
            li.addContextMenuItems([(_(30010), 'RunPlugin(%s)' % self.url(action='remove_search', term=term))])
            xbmcplugin.addDirectoryItem(self.handle, self.url(action='search_results', query=term), li, True)
        if terms:
            self.add_folder(_(30004), self.url(action='clear_search'), 'DefaultIconError.png')
        self.end(cache=False)

    def do_new_search(self):
        query = xbmcgui.Dialog().input(_(30003), type=xbmcgui.INPUT_ALPHANUM).strip()
        if not query:
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            return
        self.history.add(query)
        self.list_shows(self.api.search_shows(query))

    def do_search_results(self):
        self.list_shows(self.api.search_shows(self.params['query']))

    def do_remove_search(self):
        self.history.remove(self.params['term'])
        xbmc.executebuiltin('Container.Refresh')

    def do_clear_search(self):
        self.history.clear()
        xbmc.executebuiltin('Container.Update(%s,replace)' % self.url(action='search'))

    # ---------------------------------------------------------- favourites

    def do_add_favourite(self):
        self.favourites.add(json.loads(self.params['show']))
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), _(30008), ICON, 2000)

    def do_remove_favourite(self):
        self.favourites.remove(self.params['slug'])
        xbmc.executebuiltin('Container.Refresh')

    # ------------------------------------------------------------ playback

    def do_play(self):
        url = self.params['url']
        li = xbmcgui.ListItem(path=url)
        if '.m3u8' in url:
            li.setMimeType('application/vnd.apple.mpegurl')
            li.setContentLookup(False)
        captions = self.params.get('captions')
        if captions:
            li.setSubtitles([captions])
        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def do_clear_cache(self):
        self.api.clear_cache()
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), _(30014), ICON, 2000)

    # ------------------------------------------------------------- helpers

    def list_shows(self, shows):
        fav_slugs = {s.get('slug') for s in self.favourites.load()}
        for show in shows:
            li = xbmcgui.ListItem(show['title'], offscreen=True)
            image = show.get('image') or ICON
            li.setArt({'thumb': image, 'icon': image, 'poster': image, 'fanart': FANART})
            plot = show.get('plot', '')
            if show.get('age'):
                plot = '[B]Ages %s[/B]\n%s' % (show['age'], plot)
            _set_info(li, {'title': show['title'], 'plot': plot, 'mediatype': 'tvshow'})
            if show['slug'] in fav_slugs:
                menu = (_(30009), 'RunPlugin(%s)' % self.url(action='remove_favourite', slug=show['slug']))
            else:
                menu = (_(30008), 'RunPlugin(%s)' % self.url(action='add_favourite', show=json.dumps(show)))
            li.addContextMenuItems([menu])
            xbmcplugin.addDirectoryItem(self.handle, self.url(action='show', slug=show['slug'], title=show['title']),
                                        li, isFolder=True)
        if not shows:
            xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), _(30011), ICON, 2000)
        xbmcplugin.setContent(self.handle, 'tvshows')
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
        self.end(cache=False)

    def add_folder(self, label, url, icon):
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': icon, 'thumb': icon, 'fanart': FANART})
        xbmcplugin.addDirectoryItem(self.handle, url, li, isFolder=True)

    def end(self, cache=True):
        xbmcplugin.endOfDirectory(self.handle, cacheToDisc=cache)


def _set_info(li, info):
    """Use the InfoTagVideo API on Kodi 20+, fall back to setInfo on Kodi 19."""
    info = {k: v for k, v in info.items() if v}
    getter = getattr(li, 'getVideoInfoTag', None)
    if getter is None:
        li.setInfo('video', info)
        return
    tag = getter()
    setters = {'title': 'setTitle', 'plot': 'setPlot', 'duration': 'setDuration',
               'aired': 'setFirstAired', 'tvshowtitle': 'setTvShowTitle', 'mediatype': 'setMediaType'}
    for key, value in info.items():
        if key in setters:
            getattr(tag, setters[key])(value)


def run(argv):
    Router(argv).dispatch()
