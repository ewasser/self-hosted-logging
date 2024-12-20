import hashlib
import io
import json

from pathlib import Path
from datetime import datetime


class FileCacheEntry:
    def __init__(self, cache, name):
        self.cache = cache
        self.name = name

    def __repr__(self):
        return '{!s}/{!s}'.format(self.cache.cache_directory, self.name)

    @property
    def path(self) -> Path:
        return self.cache.cache_directory / self.name

    def fresh(self, mtime=None):
        if not self.path.exists():
            return False

        if mtime:
            if self.path.stat().st_mtime < mtime:
                return False

        return True

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        if mode[0] == 'w':
            parent_directory = self.path.parent

            if not parent_directory.exists():
                parent_directory.mkdir(parents=True, exist_ok=True)

        return io.open(self.path, mode, buffering, encoding, errors, newline, closefd, opener)


class FileCache:
    def __init__(self, cache_directory=None):
        self.app = None
        self.cache_directory = cache_directory

    @staticmethod
    def aaaa(name: str, extension: str = None):

        sha256_hash = hashlib.sha256()
        sha256_hash.update(name.encode('utf8'))
        hex_digest = sha256_hash.hexdigest()

        if extension:
            hex_digest += extension

        return Path(hex_digest[0] + '/' + hex_digest[1] + '/' + hex_digest[2] + '/' + hex_digest)

    def get(self, key, extension=None):
        return FileCacheEntry(
            cache=self,
            name=FileCache.aaaa(key, extension=extension),
        )

    def init_app(self, app):
        self.app = app

        self.cache_directory = Path.home() / '.cache' / app.name


class Entry:
    def __init__(self, filename, attributes=None):
        self.filename = filename
        self.attributes = attributes

    def _data(self):
        return {
            'filename': self.filename,
            'attributes': self.attributes,
        }

    @property
    def cache_filename(self):

        data = json.dumps(self._data(), sort_keys=True)

        readable_hash = hashlib.sha256(data.encode('utf8')).hexdigest();

        return Path(readable_hash)


class Cache:
    def __init__(self):
        self.app = None
        self.cache_directory = None

    def init_app(self, app):
        self.app = app

        self.cache_directory = Path.home() / '.config' / app.name

    def entry(self, filename, attributes=None):
        return self.cache_directory / Entry(filename, attributes).cache_filename


# cache = Cache()
cache = FileCache()

