import os, tempfile
PROFILE = tempfile.mkdtemp()
SETTINGS = {'cache_hours': '0', 'page_size': '2', 'subtitles': 'true'}
class Addon(object):
    def getAddonInfo(self, key):
        return {'id': 'plugin.video.pbskids', 'name': 'PBS Kids', 'profile': PROFILE,
                'icon': 'icon.png', 'fanart': 'fanart.jpg'}[key]
    def getSetting(self, key): return SETTINGS.get(key, '')
    def getLocalizedString(self, sid): return 'S%d' % sid
