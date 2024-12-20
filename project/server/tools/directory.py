import fs
import re

PATTERN_PICTURES = re.compile('\\.jpg$', re.IGNORECASE)


class Stats:
    def __init__(self):
        self.pictures = 0


class Directory:
    def __init__(self, url, path):
        self.stats = Stats()
        self.url = url
        self.path = path

    def scandir(self, only_files=True, pattern=None):

        filesystem = fs.open_fs(self.url)
        filesystem_content = list(filesystem.filterdir(
            self.path,
            exclude_dirs=['*'],
        ))

        for entry in filesystem_content:

            if pattern is None or pattern.search(entry.name):
                result = PATTERN_PICTURES.search(entry.name)

                if result:
                    self.stats.pictures += 1

                yield entry
