INPUT_ALPHANUM, NOTIFICATION_ERROR = 0, 'error'
notifications = []
input_value = ''
class ListItem(object):
    def __init__(self, label='', path='', offscreen=False):
        self.label, self.path, self.art, self.info, self.props = label, path, {}, {}, {}
        self.menu, self.subtitles, self.mime = [], [], None
    def setArt(self, art): self.art.update(art)
    def setInfo(self, kind, info): self.info.update(info)
    def setProperty(self, k, v): self.props[k] = v
    def addContextMenuItems(self, items): self.menu.extend(items)
    def setSubtitles(self, subs): self.subtitles = subs
    def setMimeType(self, m): self.mime = m
    def setContentLookup(self, v): pass
class Dialog(object):
    def notification(self, *a, **k): notifications.append(a)
    def input(self, heading, type=0): return input_value
