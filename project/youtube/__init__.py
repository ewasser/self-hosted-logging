import hashlib
import io
from builtins import super
from collections import UserDict
from functools import partial
from pathlib import Path
import urllib.parse

import requests as requests
from PIL import Image
from diskcache import Cache
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user

from project.server.database import db
from project.server.models import YoutubeVideo

youtube_blueprint = Blueprint(
    'youtube',
    __name__,
    template_folder='templates',
    static_folder='static'
)

BUFFER_SIZE = 65_536

from enum import IntEnum
class YoutubeLinkType(IntEnum):
    UNKNOWN = 1
    VIDEO = 2


class YoutubeLink:
    def __init__(self, link):
        self.link = link
        self.kind = YoutubeLinkType.UNKNOWN

        self.video_id = None

        self._analyze()

    def _analyze(self):
        o = urllib.parse.urlparse(self.link)
        #
        if o.path == '/watch':
            params = urllib.parse.parse_qs(o.query)
            self.video_id = params['v'][0]

            self.kind = YoutubeLinkType.VIDEO

    def preview_url(self):
        if self.kind == YoutubeLinkType.VIDEO:
            return 'https://i.ytimg.com/vi/{}/maxresdefault.jpg'.format(self.video_id)

        raise ValueError()

# reader, timestamp, tag = result
#https://www.youtube.com/watch?v=bPOwpSy4-2o
#https://www.youtube.com/c/DrachenLord
#https://www.youtube.com/results?search_query=drachenlord
#https://www.youtube.com/channel/UCPGr21v3yJpKPmr_KAypHFg


@youtube_blueprint.route('/dashboard')
@login_required
def dashboard():

    ids = []

    with db.engine.connect() as con:

        rs = con.execute('SELECT MIN(id) FROM youtube_hits GROUP BY url ORDER BY mtime DESC LIMIT 20')
        for row in rs:
            ids.append(row[0])

        objects_rows = db.session.query(YoutubeVideo).\
            filter(YoutubeVideo.id.in_(ids)).\
            order_by(YoutubeVideo.id.desc()).all()

    jinja2_rows = []

    for row in objects_rows:

        youtube_link = YoutubeLink(row.url)

        jinja2_rows.append({
            'kind': youtube_link.kind.name,
            'id': row.id,
            'title': row.title,
            'mtime': row.mtime,
            'link': row.url,
            'preview': url_for('youtube.thumbnail', youtubehit_id=row.id),
            'thumbnail': {
                'id': row.id,
            }
        })

    p = {
        'head': {
            'title': 'Youtube1',
        },
        'page': {
            'title': 'Youtube2 Dashboard 🐍',
        },
        'current_user': current_user,
        'rows': jinja2_rows,
    }
    return render_template('youtube-dashboard.jinja2', **p)
