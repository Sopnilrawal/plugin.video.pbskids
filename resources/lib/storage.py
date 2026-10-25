# -*- coding: utf-8 -*-
"""Small JSON-file stores for favourites and search history (no Kodi imports)."""
import json
import os


class JsonList(object):

    def __init__(self, path, limit=None):
        self.path = path
        self.limit = limit

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (IOError, OSError, ValueError):
            return []

    def save(self, items):
        folder = os.path.dirname(self.path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        if self.limit:
            items = items[:self.limit]
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=1)

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)


class Favourites(JsonList):
    """Favourite shows, keyed by slug, most recently added first."""

    def contains(self, slug):
        return any(s.get('slug') == slug for s in self.load())

    def add(self, show):
        items = [s for s in self.load() if s.get('slug') != show['slug']]
        self.save([show] + items)

    def remove(self, slug):
        self.save([s for s in self.load() if s.get('slug') != slug])


class SearchHistory(JsonList):
    """Search terms, newest first, case-insensitive de-duplication."""

    def add(self, term):
        term = term.strip()
        if term:
            items = [t for t in self.load() if t.lower() != term.lower()]
            self.save([term] + items)

    def remove(self, term):
        self.save([t for t in self.load() if t != term])
