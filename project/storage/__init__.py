import mimetypes
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import fs
import fs.errors
import humanize
from flask import Blueprint, render_template, abort, url_for, redirect, jsonify, send_file
from flask import current_app as app, request
from flask_login import login_required, current_user

from project.middleware.storages import Storages, StorageLocation, normalize_path

storage_blueprint = Blueprint(
    'storage',
    __name__,
    template_folder='templates',
    static_folder='static'
)

PATTERN_PICTURES = re.compile(r"\.(jpe?g|png|gif)$", re.IGNORECASE)

PATTERNS = {
    'pictures': re.compile(r"\.(jpe?g|png|gif)$", re.IGNORECASE),
    'music': re.compile(r"\.(mp3|ogg|wav)$", re.IGNORECASE),
    'videos': re.compile(r"\.(mp4|avi)$", re.IGNORECASE),
    'documents': re.compile(r"\.(txt|md)$", re.IGNORECASE),
}


class MultiPatternMatching:

    def __init__(self, patterns):
        self.patterns = patterns

    def generate(self, files):

        types = {}

        for name in self.patterns.keys():
            types[name] = 0

        for file in files:
            for name, pattern in self.patterns.items():
                if pattern.search(file):
                    types[name] += 1

        return types

    @staticmethod
    def detect_type(filename: str):
        for name, pattern in PATTERNS.items():
            if pattern.search(filename):
                return name

        return None

"""

We're dealing with 4 kind of stuff:

* Pictures
* Music
* Videos
* Documents

"""


def rows__(n, elements):
    row = []

    for e in elements:
        row.append(e)
        if len(row) == n:
            yield row
            row = []

    if len(row) >= 1:
        yield row


@storage_blueprint.route('/')
@login_required
def root():
    return redirect(url_for(".dashboard"))


@storage_blueprint.route('/dashboard')
@login_required
def dashboard():

    storages = Storages(app.config['STORAGES'])

    storage_cards = []

    for s in storages.storages:
        storage_cards.append({
            'name': s.name,
            'content': s.description,
            'url': url_for('.tree', storage_name=s.name, path='/')
        })

    p = {
        'head': {
            'title': 'Dashboard Storages',
        },
        'body': {
            'title': 'Dashboard Storages',
        },
        'current_user': current_user,
        'storage_rows': rows__(4, storage_cards),
    }
    return render_template('storage-dashboard.html', **p)


@storage_blueprint.route('/file/<string:storage_name>/<path:path>')
@login_required
def file(storage_name, path):

    path = normalize_path(path)

    storage = Storages(app.config['STORAGES']).get_storage(urllib.parse.unquote(storage_name))

    filesystem = fs.open_fs(storage.fs_identifier)

    handle = filesystem.open(str(path), mode='rb')

    (path_mimetype, path_encoding) = mimetypes.guess_type(path, strict=True)

    return send_file(handle, mimetype=path_mimetype)


@dataclass
class Button:
    """Class for keeping track of an item in inventory."""
    text: str
    cls: str
    target: str
    icon: str


@dataclass
class ButtonGroup:
    buttons: list

    def __len__(self):
        return len(self.buttons)


@dataclass
class DirectoryContentEntry:
    def __init__(self, location, kind, mtime, size):
        if location is None:
            raise ValueError("'location' can't be None")

        self.location: StorageLocation = location
        self.kind = kind
        self.mtime = mtime
        self.size = size

    @property
    def path(self):
        return self.location.path

    @property
    def is_file(self):
        return self.kind == 'file'

    @property
    def is_dir(self):
        return self.kind == 'dir'

    @property
    def file_type(self):
        return MultiPatternMatching.detect_type(str(self.path))

    def __repr__(self):
        return '{!s} (t: {}, s: {})'.format(self.location, self.kind, self.size)


class DirectoryContent:

    def __init__(self, storage_location: StorageLocation):
        app.logger.debug("fs.open_fs({}:{})".format(
            storage_location.storage,
            storage_location.path))

        self.storage_location = storage_location
        self.content = []
        self._statistics = None

    def read(self):

        statistics_dirs = 0
        statistics_files = 0
        statistics_bytes = 0

        filesystem = fs.open_fs(self.storage_location.storage.fs_identifier)

        for filesystem_entry in filesystem.scandir(
                str(self.storage_location.path), namespaces=['basic', 'details']):

            kind = 'file'

            if filesystem_entry.is_dir:
                kind = 'dir'

            dce = DirectoryContentEntry(
                location=self.storage_location / filesystem_entry.name,
                kind=kind,
                mtime=filesystem_entry.modified,
                size=filesystem_entry.size,
            )

            if dce.is_dir:
                statistics_dirs += 1
            if dce.is_file:
                statistics_files += 1
            statistics_bytes += dce.size

            self.content.append(dce)

        app.logger.info(self.content)

        self.content.sort(key=lambda k: k.location.path.name)

        self._statistics = {
            'dirs': statistics_dirs,
            'files': statistics_files,
            'bytes': statistics_bytes,
            'types': None,
        }

    @property
    def statistics(self):

        if self._statistics['types'] is not None:
            return self._statistics

        types = MultiPatternMatching(patterns=PATTERNS)
        types2 = types.generate(map(lambda x: str(x.location.path.name), self.content))

        self._statistics['types'] = sorted(
            types2.items(), key=lambda item: item[1], reverse=True
        )

        return self._statistics

    def match(self, pattern: re.Pattern):
        return filter(lambda x: pattern.search(x.name), self.content)


@storage_blueprint.route('/content/<string:storage_name>', defaults={'path': '/'})
@storage_blueprint.route('/content/<string:storage_name>/', defaults={'path': '/'})
@storage_blueprint.route('/content/<string:storage_name>/<path:path>')
@login_required
def content(storage_name, path):
    """
    This function will return alle the needed information for your given view:
    * pictures | music | videos | documents

    We will return a big dictionary with all the content you need:

    {
        'storage': {
            'name': str(storage_location.storage.name),
            'path': str(storage_location.path),
        },
        'view': {
            'name': view_name,
            'tab': {
                'content': …HTML CODE…,
            },
            'buttons': {
                'main': …HTML CODE…,
            }
        },
        'statistics': statistics,
    }
    """

    path = normalize_path(path)

    storage = Storages(app.config['STORAGES']).get_storage(urllib.parse.unquote(storage_name))

    storage_location = StorageLocation(
        storage=storage,
        path=path,
    )

    try:
        directory_content = DirectoryContent(storage_location)
        directory_content.read()
    except fs.errors.ResourceNotFound:
        abort(503)

    statistics = directory_content.statistics
    types = statistics['types']

    view_name = 'documents'

    if len(types) >= 1:
        view_name = types[0][0]

    #   Global buttons...
    buttons_main = []

    if storage_location.path != '/':

        parent_of_name = storage_location.path.parent
        if parent_of_name == '.':
            parent_of_name = Path("/")

        buttons_main.append(Button(
            cls='',
            icon='arrow-up',
            text='Up',
            target=url_for('.tree', storage_name=storage_location.storage.name, path=parent_of_name),
        ))

    rendering_parameter = {
        'storage': {
            'name': str(storage_location.storage.name),
            'path': str(storage_location.path),
        },
        'view': {
            'name': view_name,
            'tab': generate_tab_for_view(view_name, directory_content.content),
            'buttons': {
                'main': render_template('storage-view-buttons.jinja2', buttons=buttons_main),
            }
        },
        'statistics': statistics,
    }

    return jsonify(
        **rendering_parameter
    )


@storage_blueprint.route('/tree/<string:storage_name>', defaults={'path': '/'})
@storage_blueprint.route('/tree/<string:storage_name>/', defaults={'path': '/'})
@storage_blueprint.route('/tree/<string:storage_name>/<path:path>')
@login_required
def tree(storage_name, path):
    """
    #   Examples from gitlab.com
    https://foo.home/group_name/project_name/-/tree/master
    https://foo.home/group_name/project_name/-/tree/master/directory
    https://foo.home/group_name/project_name/-/blob/master/.gitlab-ci.yml
    https://foo.home/group_name/project_name/-/raw/master/.gitlab-ci.yml?inline=false
    https://foo.home/group_name/project_name/-/raw/master/.gitlab-ci.yml
    """

    path = normalize_path(path)

    app.logger.info("Calling Tree '{}:{}'".format(storage_name, path))

    mode = request.args.get('mode', default='1', type=str)

    #   TODO: Check mode

    storage = Storages(app.config['STORAGES']).get_storage(urllib.parse.unquote(storage_name))

    storage_location = StorageLocation(
        storage=storage,
        path=path,
    )

    title = '{!r}'.format(storage_location)

    # try:
    #     directory_content = DirectoryContent(storage.fs_identifier, storage_location.path)
    #     directory_content.read()
    # except fs.errors.ResourceNotFound as e:
    #     app.logger.error(e)
    #     abort(503)

    buttons = []
    entries = []

    pictures = 0
    pics = []

    if storage_location.path != '/':

        parent_of_name = Path(storage_name).parent
        if parent_of_name == '.':
            parent_of_name = Path("/")

        buttons.append({
            'icon': 'arrow-up',
            'text': 'Up',

            'target': url_for('.tree', storage_name=storage_location.storage.name, path=parent_of_name),
        })

    # button_group = ButtonGroup(buttons=[
    #     Button(text='thdfhdhd', cls='', href='https://www.spiegel.de', icon='fa-list'),
    #     Button(text='t', cls='', href='href', icon='fa-image'),
    # ])

    # button_groups = [
    #     button_group
    # ]

    # pictures = []
    # gallery_images = []
    # p = list(enumerate(directory_content.match(PATTERN_PICTURES), 1))
    #
    # for number, directory_content_entry in p:
    #     tags = []
    #
    #     suffix = Path(directory_content_entry.name).suffix
    #     if suffix:
    #         tags.append(suffix[1:])
    #
    #     pictures.append({
    #         'number': number,
    #         'urls': {
    #             'thumbnail': url_for('gallery.thumbnail', name=storage_name, path=str(directory_content_entry.full_name)),
    #         },
    #         'tags': tags,
    #         'mtime': {
    #             'machine': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
    #             'human': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
    #         },
    #     })
    #
    #     gallery_images.append({
    #         'link_picture': url_for('.tree', storage_name=storage_name, path=directory_content_entry.full_name),
    #         'caption': '{} ({} of {})'.format(
    #             directory_content_entry.name,
    #             number,
    #             len(p)
    #         ),
    #     })

    # if len(pictures) >= 1:
    #     buttons.append({
    #         'icon': 'images',
    #         'text': 'Gallery',
    #
    #         'id': 'gallery-button',
    #         'target': '#',
    #     })

    p = {
        'head': {
            'title': title,
        },
        'body': {
            'title': title,
        },
        'current_user': current_user,
        'storage': {
            'name': storage_name,
        },
        # 'directory_listing_rows': directory_listing_rows,
        # 'gallery_images': json.dumps(gallery_images),
        'gallery_images': [],
        # 'button_groups': button_groups,
        #'rows': rows__(4, pictures),
        'PAGE_GLOBALS': {
            'content': url_for('.content', storage_name=storage_name, path=path),
            'storage': {
                'name': storage_name,
                'path': str(path),
            },
        }
    }

    return render_template('storage-index.jinja2', **p)


# def generate_document_rows(storage_location: StorageLocation):
#
#     try:
#         directory_content = DirectoryContent(storage_location.storage.fs_identifier, storage_location.path)
#         directory_content.read()
#     except fs.errors.ResourceNotFound:
#         abort(503)
#
#     view_rows = []
#
#     for directory_content_entry in directory_content.content:
#
#         #   entry_icon is the name of the image (from fontawesome)
#         #   entry_type is the internal naming for a file/dir
#         (entry_icon, entry_type) = ('file', 'file')
#
#         if directory_content_entry.is_dir:
#             (entry_icon, entry_type) = ('folder', 'dir')
#
#         entry = {
#             'columns': {
#                 'type': {
#                     'icon': entry_icon,
#                     'type': entry_type,
#                 },
#                 'name': {
#                     'full_name': str(directory_content_entry.full_name),
#                     'name': str(directory_content_entry.name),
#                     'path': str(directory_content_entry.path),
#                 },
#                 'info': {
#                     'modified': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
#                     'modified_human': humanize.naturalday(directory_content_entry.mtime),
#                 },
#                 'buttons': [],
#             }
#         }
#         view_rows.append(entry)

    # if storage_location.path != '/':
    #
    #     parent_of_name = Path(storage_name).parent
    #     if parent_of_name == '.':
    #         parent_of_name = Path("/")
    #
    #     buttons.append({
    #         'icon': 'arrow-up',
    #         'text': 'Up',
    #
    #         'target': url_for('.tree', storage_name=storage_location.storage.name, path=parent_of_name),
    #     })

    # button_group = ButtonGroup(buttons=[
    #     Button(text='thdfhdhd', cls='', href='https://www.spiegel.de', icon='fa-list'),
    #     Button(text='t', cls='', href='href', icon='fa-image'),
    # ])
    #
    # button_groups = [
    #     button_group
    # ]

    # pictures = []
    # gallery_images = []
    # p = list(enumerate(directory_content.match(PATTERN_PICTURES), 1))
    #
    # for number, directory_content_entry in p:
    #     tags = []
    #
    #     suffix = Path(directory_content_entry.name).suffix
    #     if suffix:
    #         tags.append(suffix[1:])
    #
    #     pictures.append({
    #         'number': number,
    #         'urls': {
    #             'thumbnail': url_for('gallery.thumbnail', name=storage_name, path=str(directory_content_entry.full_name)),
    #         },
    #         'tags': tags,
    #         'mtime': {
    #             'machine': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
    #             'human': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
    #         },
    #     })
    #
    #     gallery_images.append({
    #         'link_picture': url_for('.tree', storage_name=storage_name, path=directory_content_entry.full_name),
    #         'caption': '{} ({} of {})'.format(
    #             directory_content_entry.name,
    #             number,
    #             len(p)
    #         ),
    #     })
    #
    # if len(pictures) >= 1:
    #     buttons.append({
    #         'icon': 'images',
    #         'text': 'Gallery',
    #
    #         'id': 'gallery-button',
    #         'target': '#',
    #     })

    # return render_template('storage-view-documents.jinja2',
    #                        rows=view_rows,
    #                        )


def generate_tab_for_view(view_name, files):
    """
    We must return the 'tab' content:
    * This is a hash with the key `content`
     'tab': generate_tab_for_view(view_name, directory_content.content),

    """
    tab = None
    rows = None

    def file_filter(dce: DirectoryContentEntry):
        return MultiPatternMatching.detect_type(dce.path.name) == view_name or dce.is_dir

    files = filter(lambda dce: file_filter(dce), files)

    if view_name == 'pictures':
        tab, rows = generate_tab_data_for_pictures(files)
    elif view_name == 'music':
        pass
    elif view_name == 'videos':
        pass
    elif view_name == 'documents':
        tab, rows = generate_tab_data_for_documents(files)

    if tab is None or rows is None:
        raise ValueError()

    full_view_name = 'storage-view-{}.jinja2'.format(view_name)

    tab['content'] = render_template(full_view_name,
                                     rows=rows)

    return tab


def generate_tab_data_for_documents(files):

    rows = []

    for directory_content_entry in files:

        app.logger.error("foo = {!s}".format(directory_content_entry))

        #   entry_icon is the name of the image (from fontawesome)
        #   entry_type is the internal naming for a file/dir
        (entry_icon, entry_type) = ('file', 'file')

        if directory_content_entry.is_dir:
            (entry_icon, entry_type) = ('folder', 'dir')

        file_type = directory_content_entry.file_type

        buttons = []

        if file_type == 'documents':
            buttons.append(Button(
                text='Edit',
                cls='is-primary',
                target=url_for(".dashboard"),
                icon='fa-edit')
            )

        if directory_content_entry.is_dir:
            buttons.append(Button(
                text='Enter',
                cls='is-link',
                target=url_for('.tree',
                               storage_name=directory_content_entry.location.storage.name,
                               path=directory_content_entry.location.path),
                icon='fa-edit')
            )

        entry = {
            'columns': {
                'type': {
                    'icon': entry_icon,
                    'type': entry_type,
                },
                'name': {
                    'location': {
                        'name': str(directory_content_entry.location.storage.name),
                        'path': str(directory_content_entry.location.path),
                    },
                    'name': str(directory_content_entry.location.path.name),
                },
                'info': {
                    'modified': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    'modified_human': humanize.naturalday(directory_content_entry.mtime),
                },
                'buttons': buttons,
            }
        }
        rows.append(entry)

    return {}, rows


def generate_tab_data_for_pictures(files):

    rows = []

    for number, directory_content_entry in enumerate(files, start=1):

        if directory_content_entry.is_file:
            entry = {
                'is_file': True,
                'is_dir': False,
                'headlines': {
                  'number': '#{}'.format(number),
                  'filename': directory_content_entry.path.name,
                  'tags': ['a', 'b', 'c'],
                },
                'previewpic': url_for('gallery.thumbnail',
                                      storage_name=directory_content_entry.location.storage.name,
                                      path=directory_content_entry.location.path),
                'minipic': 'https://bulma.io/images/placeholders/96x96.png',
                'description': '',
                'filedate': {
                    'datetime': directory_content_entry.mtime.strftime('%Y-%m-%d'),
                    'display': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
                },
            }
        elif directory_content_entry.is_dir:
            app.logger.info('{!r}'.format(directory_content_entry.location))
            entry = {
                'is_file': False,
                'is_dir': True,
                'headlines': {
                  'number': '#{}'.format(number),
                  'filename': directory_content_entry.path.name,
                  'tags': ['directory'],
                },
                'previewpic': url_for('static',  filename='directory.jpg'),
                'minipic': 'https://bulma.io/images/placeholders/96x96.png',
                'clicklink': url_for(
                    '.tree',
                    storage_name=directory_content_entry.location.storage.name,
                    path=str(directory_content_entry.path)[1:]
                ),
                'description': '',
                'filedate': {
                    'datetime': directory_content_entry.mtime.strftime('%Y-%m-%d'),
                    'display': directory_content_entry.mtime.strftime("%Y-%m-%d %H:%M:%S"),
                },
            }

        rows.append(entry)

    return {}, rows__(4, rows)
