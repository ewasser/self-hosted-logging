from dataclasses import dataclass
from pathlib import Path

from flask import abort, current_app as app


@dataclass
class Storage:
    #   Short Name
    name: str
    #   Longer Description
    description: str
    #   The identifier for the library `fs`.
    fs_identifier: str


class Storages:
    def __init__(self, storages_configuration):
        self.storages = []

        #   We're taking the configurations from config['STORAGES'] and converting
        #   them to an object.
        for s in storages_configuration:
            self.storages.append(Storage(**s))

    def get_storage(self, name):
        for unit in self.storages:
            if unit.name == name:
                return unit

        abort(404)

    @staticmethod
    def location(name, path):

        storage = Storages(app.config['STORAGES']).get_storage(name)

        return StorageLocation(storage, path)


class StorageLocation:
    def __init__(self, storage: Storage, path: Path):
        #
        self.storage = storage
        self._path = None

        self.path = path

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, p):

        p_as_string = str(p)

        if len(p_as_string) == 0:
            raise ValueError("Illegal empty path")

        if len(p_as_string) >= 2 and p_as_string[0:2] == '/-':
            p_as_string = p_as_string[2:]

        if p_as_string[0] != '/':
            raise ValueError("Path '{}' must begin with a '/'".format(p_as_string))

        self._path = Path(p_as_string)

    def clone(self):
        return StorageLocation(
            storage=self.storage,
            path=self.path,
        )

    def __truediv__(self, name):
        c = self.clone()
        c.path = c.path / name

        return c

    def parent(self):
        c = self.clone()
        c.path = c.path.parent

        return c

    def __repr__(self):
        return '{}:{}'.format(self.storage.name, self.path)


def normalize_path(p):
    """
    Rulez:
    1. We remove all but one leading '/'.
    2. We remove a trailing '/'.
    3. We remove all '//'.
    """

    if p is None:
        p = ''

    p = str(p)

    if p == '':
        p = '/'

    if p[0] == '.':
        raise ValueError("Bad path '{}'".format(p))

    if p[0] != '/':
        p = '/' + p

    return Path(p)
