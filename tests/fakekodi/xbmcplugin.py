SORT_METHOD_UNSORTED, SORT_METHOD_LABEL_IGNORE_THE = 0, 1
items, resolved, ended = [], [], []
def addDirectoryItem(handle, url, li, isFolder=False): items.append((url, li, isFolder))
def endOfDirectory(handle, succeeded=True, cacheToDisc=True): ended.append(succeeded)
def setResolvedUrl(handle, ok, li): resolved.append(li)
def setContent(handle, c): pass
def addSortMethod(handle, m): pass
def reset():
    del items[:], resolved[:], ended[:]
