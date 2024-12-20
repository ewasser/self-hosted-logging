import datetime
import json
import logging
import urllib.parse
import uuid
from pathlib import Path
import io
from subprocess import Popen, PIPE


from diskcache import Cache
from flask import Blueprint, current_app, send_file, make_response, \
    jsonify
from flask import url_for, render_template, request
from flask_login import login_required, current_user

from project.server.link import factory, LinkType

from project.server.database import db
from project.server.models import Hit, Order, Archive


logger = logging.getLogger()


"""
curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"username":"xyz","password":"xyz"}' \
  https://api.wasser.family/test
"""

hits_blueprint = Blueprint(
    'hits',
    __name__,
    template_folder='templates',
    static_folder='static'
)


def sad(youtube_id: str):

    command = [
        'bin/yi.py',
        '.',
        '--output-format=json',
        '-s',
        youtube_id
    ]

    logger.debug('Starting my youtube lookup: {}'.format(' '.join(command)))

    process = Popen(command, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    return len(stdout) > 0


@hits_blueprint.route('/collection', methods=['POST'])
@login_required
def store():
    if request.method == 'POST':

        data = request.json

        if not isinstance(data, dict):
            d = {
                'status': 'ERROR',
                'message': 'No hash',
            }
            return make_response(jsonify(d), 200)

        if 'hits' not in data:
            d = {
                'status': 'ERROR',
                'message': "Missing hash key 'hits'",
            }
            return make_response(jsonify(d), 200)

        for r in data['hits']:

            hit = db.session.query(Hit).filter(Hit.url == r['url']).one_or_none()

            if hit:
                hit.visited += 1
                hit.mtime = datetime.datetime.fromtimestamp(int(r['timestamp_ms']) / 1000)
            else:
                hit = Hit(
                    url=r['url'],
                    mtime=datetime.datetime.fromtimestamp(int(r['timestamp_ms']) / 1000),
                    title=r['title'],
                    visited=1,
                )
                db.session.add(hit)

        db.session.commit()

    return {
        'status': 'OK'
    }


@hits_blueprint.route('/thumbnail/<hit_id>')
@login_required
def thumbnail(hit_id):

    hit = db.session.query(Hit).filter(Hit.id == hit_id).one_or_none()

    if hit is None:
        return

    cache_directory = Path(current_app.instance_path).parent
    cache = Cache(cache_directory / '.cache')

    link = factory(hit.url)
    thumbnail_image_stream = link.thumbnail_image_stream(cache)
    cache.close()

    if not thumbnail_image_stream:
        return

    return send_file(thumbnail_image_stream, mimetype='image/jpg')


@hits_blueprint.route('/status/<hit_id>')
@login_required
def status(hit_id):
    #
    hit = db.session.query(Hit).filter(Hit.id == hit_id).one_or_none()
    #
    if hit is None:
        return jsonify(status={'code': '?'})

    #   We know the following states:
    #   1) Unknown kind of link
    #   2) A video link that was already downloaded
    #   3) A video link that can be downloaded
    json_hit = {
        'status': '?',
    }

    link = factory(hit.url)
    if link.video_id:

        archive_source, archive_name = link.archive()

        archive = db.session.query(Archive).where(
            Archive.source == archive_source,
            Archive.name == archive_name,
        ).one_or_none()

        if archive or sad(link.video_id):
            json_hit['status'] = 'was-downloaded'
        else:
            json_hit['status'] = 'can-be-downloaded'
            json_hit['download_url'] = url_for('hits.download', hit_id=hit.id)

    return jsonify(hit=json_hit)


@hits_blueprint.route('/download/<hit_id>', methods=['POST'])
@login_required
def download(hit_id):

    hit = db.session.query(Hit).filter(Hit.id == hit_id).one_or_none()

    if hit is None:
        return jsonify(status={'text': 'not found'})

    order_uuid = uuid.uuid4()
    registered_on = datetime.datetime.now()

    link = factory(hit.url)
    if link.video_id:
        order = Order(
            registered_on=registered_on,
            start_time=registered_on,
            title=hit.title,
            channel='youtube/download',
            payload=json.dumps({
                'youtube_id': link.video_id,
                'archive': {
                    'source': 'youtube',
                    'name': link.video_id,
                },
            }),
            status='new',
            uuid=str(order_uuid),
        )

        db.session.add(order)

        db.session.commit()

    return jsonify(status={'text': 'Starting Download...'})


@hits_blueprint.route('/current')
@login_required
def current():

    maximal_hits = 10

    json_rows = []

    with db.engine.begin() as con:

        ids = []

        rs = con.exec_driver_sql(
                'SELECT MIN(id) FROM hits GROUP BY url ORDER BY mtime DESC LIMIT ? OFFSET ?', (maximal_hits, 0))
        for row in rs:
            ids.append(row[0])

        objects_rows = db.session.query(Hit).\
            filter(Hit.id.in_(ids)).\
            order_by(Hit.mtime.desc()).all()

        logger.error(objects_rows)

        for row in objects_rows:

            archive = None

            link = factory(row.url)
            if link.video_id:
                archive_source, archive_name = link.archive()

                archive = db.session.query(Archive).where(
                    Archive.source == archive_source,
                    Archive.name == archive_name,
                ).one_or_none()

            json_rows.append({
                'id': row.id,
                'title': row.title,
                'mtime': row.mtime.strftime("%Y-%m-%d %H:%M:%S"),
                'link': row.url,
                'url': url_for('.download', _external=True, hit_id=row.id),
                'archive': True if archive else False,
            })

    return jsonify(queue=json_rows)


class Page:
    def __init__(self, offset):
        self.offset = offset
        self.limit = 20

    @property
    def valid(self):
        if self.offset >= 0:
            return True

        return False

    def prev(self):
        return Page(offset=self.offset-self.limit)

    def next(self):
        return Page(offset=self.offset+self.limit)


@hits_blueprint.route('/dashboard')
@login_required
def dashboard():

    # https://medium.com/@pgjones/an-asyncio-socket-tutorial-5e6f3308b8b0
    ids = []

    sql_offset = request.args.get("offset", default=0, type=int)

    page = Page(sql_offset)

    navigation = {
        'left': {
            'disabled': not page.prev().valid,
            'url': url_for('.dashboard', offset=page.prev().offset),
        },
        'right': {
            'disabled': not page.next().valid,
            'url': url_for('.dashboard', offset=page.next().offset),
        }
    }

    with db.engine.begin() as con:

        rs = con.exec_driver_sql(
                'SELECT MIN(id) FROM hits GROUP BY url ORDER BY mtime DESC LIMIT ? OFFSET ?', (page.limit, page.offset))
        for row in rs:
            ids.append(row[0])

        objects_rows = db.session.query(Hit).\
            filter(Hit.id.in_(ids)).\
            order_by(Hit.mtime.desc()).all()

    jinja2_rows = []

    for row in objects_rows:

        youtube_link = factory(row.url)

        #   video
        #   list-music
        icon_title = 'question'

        database_name = ''
        database_id = ''

        if youtube_link.kind == LinkType.VIDEO:
            icon_title = 'video'
            database_name = 'youtube'
            database_id = youtube_link.video_id

        jinja2_rows.append({
            'kind': youtube_link.kind.name,
            'id': row.id,
            'icon_title': icon_title,
            'title': row.title,
            'mtime': row.mtime.strftime("%Y-%m-%d %H:%M:%S"),
            'link': row.url,
            'preview': url_for('hits.thumbnail', hit_id=row.id),
            'thumbnail': {
                'id': row.id,
            },
            'status_url': url_for('hits.status', hit_id=row.id),
            'database_name': database_name,
            'database_id': database_id,
        })

    p = {
        'head': {
            'title': 'Hits',
        },
        'page': {
            'title': 'Hits Dashboard 🐍',
        },
        'navigation': navigation,
        'current_user': current_user,
        'rows': jinja2_rows,
        'json_data': json.dumps({'foobar': 1, 'test': '<&;">'}),
    }

    return render_template('hits-dashboard.jinja2', **p)

