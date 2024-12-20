import json

from functools import partial
import tempfile
import datetime
import fs
import fs.errors
from flask import Blueprint, render_template, abort, url_for, send_file
from flask import current_app as app
from flask_login import login_required, current_user
from pathlib import Path
import project.thumbnailer

import urllib.parse

from project.middleware.storages import Storages, normalize_path
from project.server.tools.cache import cache

import project.server.tools.directory
import project.server.tools.cache
import project.server.tools.image
import mimetypes

gallery_blueprint = Blueprint(
    'gallery',
    __name__,
    template_folder='templates',
    static_folder='static'
)

IMAGE_ATTRIBUTES = {
    'x': 240,
    'y': 180,
}

BUFFER_SIZE = 65536

'''
We need 3 views.

1. Download the HTML page.
2. Download a thumbnail.
3. Download an image.
'''


def get_storage(name):

    for s in app.config['STORAGES']:
        if s['name'] == name:
            return s

    abort(404)


@gallery_blueprint.route('/index/<name>', defaults={'path': '/'})
@gallery_blueprint.route('/index/<name>/<path:path>')
@login_required
def index(name, path):

    entries = []

    storage = get_storage(name)

    directory_entries = []

    try:
        directory = project.server.tools.directory.Directory(
            storage['filesystem_url'],
            path,
        )

        directory_entries = list(directory.scandir(
            pattern=project.server.tools.directory.PATTERN_PICTURES
        ))

    except fs.errors.ResourceNotFound:
        abort(503)

    directory_entries.sort(key=lambda k: k.name)

    for directory_entry in directory_entries:

        directory_entry = Path(path) / directory_entry.name

        entries.append({
            'link_picture': urllib.parse.unquote(url_for('gallery.entry', name=name, path=str(directory_entry))),
            'link_thumbnail': urllib.parse.unquote(url_for('gallery.thumbnail', storage_name=name, path=str(directory_entry))),
            'caption': directory_entry.name,
        })

    title = 'Gallery'

    # entries = entries[0:10]

    p = {
        'head': {
            'title': title,
        },
        'body': {
            'title': title,
        },
        'storage': {
            'name': name,
            'path': path,
        },
        'current_user': current_user,
        'images_json': json.dumps(entries)
    }
    return render_template('gallery-index.jinja2', **p)


@gallery_blueprint.route('/thumbnail/<string:storage_name>/<path:path>')
@login_required
def thumbnail(storage_name, path):

    storage_location = Storages.location(
        name=storage_name,
        path=normalize_path(urllib.parse.unquote(path))
    )

    filesystem = fs.open_fs(storage_location.storage.fs_identifier)

    cache_entry = cache.get(str(storage_location.path), extension='.png')

    print('{!r} maps to cache {!r}'.format(storage_location.path, cache_entry))

    is_cached = False

    if cache_entry.path.exists():
        image_resource = filesystem.getinfo(path, namespaces=['details'])
        image_resource_modified = image_resource.modified.timestamp()

        is_cached = cache_entry.fresh(mtime=image_resource_modified)

    if not is_cached:
        with tempfile.NamedTemporaryFile(delete=False) as image_local:

            temporary_file_name = image_local.name

            with filesystem.open(path, mode='rb') as image_remote:
                for chunk in iter(lambda: image_remote.read(BUFFER_SIZE), b''):
                    image_local.write(chunk)

                # while True:
                #     data_part = image_remote.read(BUFFER_SIZE)
                #
                #     if len(data_part) == 0:
                #         break
                #
                #     image_local.write(data_part)

        print("Thumbnailing '{}' -> '{!s}'".format(temporary_file_name, cache_entry))

        thumbnailer = project.thumbnailer.Thumbnailer(
            mode=project.thumbnailer.Season.CENTERED,
            size=(256, 256),
        )

        cache_file = cache_entry.open('wb+')
        thumbnailer.thumbnail(file_input=temporary_file_name, file_output=cache_file)
        cache_file.close()

        Path(temporary_file_name).unlink()

    return send_file(cache_entry.path, mimetype='image/jpeg')


@gallery_blueprint.route('/entry/<name>/<path:path>')
@login_required
def entry(name, path):

    path = urllib.parse.unquote(path)

    storage = get_storage(name)
    filesystem = fs.open_fs(storage['filesystem_url'])

    handle = filesystem.open(path, mode='rb')

    (path_mimetype, path_encoding) = mimetypes.guess_type(path, strict=True)

    return send_file(handle, mimetype=path_mimetype)
