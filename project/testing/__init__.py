import hashlib
import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from http import HTTPStatus
from pathlib import Path

from flask import Blueprint, Response, request, abort, current_app
from werkzeug.datastructures import Headers


logger = logging.getLogger()

testing_blueprint = Blueprint(
    'testing',
    __name__,
    template_folder='templates',
    static_folder='static'
)


@dataclass
class FileForSendfile:
    filename: Path
    handle: object
    size: int
    mimetype: str
    mtime: float


def generate_etag(*data):

    readable_hash = hashlib.sha256()

    for d in data:
        hashlib.sha256(d.encode()+b"\0")

    return readable_hash.hexdigest()

#
# >>> datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %Z')
# 'Tue, 10 Jan 2023 19:00:54 UTC'
# >>>
#
# Traceback (most recent call last):
#   File "<stdin>", line 1, in <module>
# AttributeError: type object 'datetime.datetime' has no attribute 'datetime'
# >>> datetime.now().strftime('%a, %d %b %Y %H:%M:%S %Z')
# 'Tue, 10 Jan 2023 20:00:12 '
# >>> datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %Z')
# 'Tue, 10 Jan 2023 19:00:54 UTC'
# >>> a=datetime.now(timezone.utc)
# >>> b=a+timedelta(seconds=3600)
# >>> a.strftime('%a, %d %b %Y %H:%M:%S %Z')
# 'Tue, 10 Jan 2023 19:01:23 UTC'
# >>> b.strftime('%a, %d %b %Y %H:%M:%S %Z')
# 'Tue, 10 Jan 2023 20:01:23 UTC'


def http_timestamp(ts: datetime):
    return ts.strftime('%a, %d %b %Y %H:%M:%S %Z')


def send_file(filezilla: FileForSendfile, cache_timeout, stream=True):
    headers = Headers()
    headers.add('Content-Disposition', 'attachment', filename=filezilla.filename)
    headers.add('Content-Transfer-Encoding', 'binary')

    status = HTTPStatus.OK
    size = filezilla.size
    begin = 0
    end = size-1

    #   GET /z4d4kWk.jpg HTTP/1.1
    #   Host: i.imgur.com
    #   Range: bytes=0-1023
    #
    #   HTTP/1.1 206 Partial Content
    #   Content-Range: bytes 0-1023/146515
    #   Content-Length: 1024
    #   …
    #   (binary content)

    if "Range" in request.headers:
        status = HTTPStatus.PARTIAL_CONTENT
        headers.add('Accept-Ranges', 'bytes')

        m = re.search(r"^bytes=(\d+)?-(\d+)?$", request.headers["Range"])

        if not m:
            abort(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)

        begin = 0
        if m.group(1) is not None:
            begin = int(m.group(1))
        end = size-1
        if m.group(2) is not None:
            end = int(m.group(2))

        if begin > end:
            abort(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)

        if end >= size:
            abort(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)

        headers.add('Content-Range', 'bytes {}-{}/{}'.format(begin, end, size))

    content_length = (end-begin)+1
    headers.add('Content-Length', str(content_length))

    #   Add mimetype
    if stream:
        mimetype = filezilla.mimetype
    else:
        mimetype = "application/octet-stream"

    # data = None
    filezilla.handle.seek(begin, os.SEEK_SET)
    # data = filezilla.handle.read(content_length)

    current_app.logger.debug("Sending {}-{}...".format(begin, end))

    def _generator():

        to_copy = content_length

        while to_copy >= 1:
            chunk = filezilla.handle.read(min(65536, to_copy))
            if len(chunk) == 0:
                return
            yield chunk
            to_copy -= len(chunk)

    response = Response(_generator(),
                        status=status,
                        mimetype=mimetype,
                        headers=headers,
                        direct_passthrough=True)

    now = datetime.now(timezone.utc)
    last_modified = http_timestamp(datetime.fromtimestamp(filezilla.mtime, timezone.utc))

    response.cache_control.public = True
    response.cache_control.max_age = int(cache_timeout)
    response.last_modified = filezilla.mtime
    response.expires = now + timedelta(seconds=cache_timeout)
    response.set_etag(generate_etag(str(filezilla.filename), str(last_modified)))
    response.make_conditional(request)

    return response


@testing_blueprint.route('/sendfile/')
def file():
    # data = ''.join(list(map(lambda x: '{0:02x}'.format(x), range(0, 256))))
    data = bytes.fromhex(''.join(list(map(lambda x: '{0:02x}'.format(x), range(0, 256)))))

    file_for_sendfile = FileForSendfile(
        filename=Path('/test'),
        handle=io.BytesIO(data),
        size=len(data),
        mimetype="application/octet-stream",
        mtime=5.0,
    )

    return send_file(file_for_sendfile, 3600, stream=True)


@testing_blueprint.route('/video/')
def video():

    f = Path('/mnt/minime/tank0/mp3/youtube/Fernanda Pistelli @ Equinox Sessions for Techgnosis.youtube-Yysz2dMyvC8.webm')
    # f = Path("/mnt/minime/tank0/mp3/youtube/NA - Back To The 80's - Deep House Remixes Of 80's Hits.youtube-w6v7lA__DWs.mp4")

    file_for_sendfile = FileForSendfile(
        filename=f,
        handle=io.open(f, 'rb+'),
        size=f.stat().st_size,
        mimetype='video/mp4',
        mtime=f.stat().st_mtime,
    )

    return send_file(file_for_sendfile, 3600, stream=True)

