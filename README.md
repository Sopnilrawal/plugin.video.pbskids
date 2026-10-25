# PBS Kids for Kodi

A Kodi video add-on for free PBS Kids episodes and clips. Version 4 is a rewrite for
**Kodi 19 (Matrix) and newer** (Python 3) and needs no other add-ons.

## Features
- **Shows A–Z**, each with **Episodes** and **Clips**, loaded one page at a time
- **Search** shows, with a search history (you can remove single entries or clear it all)
- **Favourite shows**: right-click a show → *Add to favourite shows*
- Subtitles (SRT/WebVTT) when PBS provides them
- HLS streams when available, otherwise the best MP4
- Responses are cached on disk (cache length is a setting, and there's a *Clear cache* action)

## Layout
| File | Purpose |
|---|---|
| `default.py` | Entry point |
| `resources/lib/api.py` | PBS Kids API client. All endpoint URLs and JSON parsing live here (no Kodi imports) |
| `resources/lib/router.py` | Kodi menus, playback, context menus |
| `resources/lib/storage.py` | Favourites and search history (JSON files in the add-on profile) |
| `tests/` | Offline tests that use fake `xbmc*` modules |

## Running the tests
```
python3 -m unittest discover tests -v
```

## Install
Zip the folder as `plugin.video.pbskids/…` and use *Add-ons → Install from zip file*.
PBS Kids may only stream to US addresses.
