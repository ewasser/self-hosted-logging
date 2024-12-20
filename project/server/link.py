import hashlib
import io
import json
import logging
import subprocess
import urllib.parse
from builtins import super
from enum import IntEnum
from http import HTTPStatus

import requests as requests
from PIL import Image
from flask import Blueprint

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


def working_checksum(i):

    if isinstance(i, str):
        description = [i]
    else:
        description = list(i)

    filename_hash = hashlib.sha256(b''.join(map(lambda x: x.encode() + b"\0", description)))
    filename_hex_digest = filename_hash.hexdigest()

    return filename_hex_digest


class LinkType(IntEnum):
    UNKNOWN = 1
    VIDEO = 2
    PLAYLIST = 3


class Link:
    PREVIEW_IMAGE_SIZE = (256, 256)
    #   We need the following arguments for a link:
    #   hoster      →   youtube.com
    #   video_id    →   1234567890
    #  
    #

    def __init__(self, link):
        self.link = link
        self.kind = LinkType.UNKNOWN

        self.video_id = None

        self.analyze()

    def analyze(self):
        pass

    def thumbnail_image_stream(self, cache):

        logger.debug('1')

        thumbnail_description = 'Create thumbnail from preview image for video {}'.format(self.video_id)
        thumbnail_hex_digest = working_checksum(thumbnail_description)
        logger.debug(thumbnail_description)

        if thumbnail_hex_digest not in cache:

            preview_description = 'Download preview image for video {}'.format(self.video_id)
            preview_hex_digest = working_checksum(preview_description)
            logger.debug(preview_description)

            if preview_hex_digest not in cache:
                preview_image_stream = self.preview_stream()

                if preview_image_stream is None:
                    return None

                cache.set(preview_hex_digest, preview_image_stream, read=True)
                preview_image_stream.seek(0, io.SEEK_SET)
            else:
                preview_image_stream = cache.get(preview_hex_digest, read=True)

            if preview_image_stream is None:
                return

            image = Image.open(preview_image_stream)
            image.thumbnail(Link.PREVIEW_IMAGE_SIZE)
            file_out = io.BytesIO(b'')
            image.save(file_out, format='JPEG')
            file_out.seek(0, io.SEEK_SET)

            cache.set(thumbnail_hex_digest, file_out, read=True)
            file_out.seek(0, io.SEEK_SET)
            thumbnail_image_stream = file_out
        else:
            thumbnail_image_stream = cache.get(thumbnail_hex_digest, read=True)

        return thumbnail_image_stream


class Youtube(Link):
    def __init__(self, link):
        super().__init__(link)

#    @staticmethod
#   def analyse(url):
#       

    def archive(self):
        return 'youtube', self.video_id

    def analyze(self):
        o = urllib.parse.urlparse(self.link)

        if o.netloc in ('www.youtube.com', 'youtube.com') and o.path == '/watch':
            params = urllib.parse.parse_qs(o.query)
            self.video_id = params['v'][0]
            self.kind = LinkType.VIDEO

    @staticmethod
    def _binary_stream_from_response(response):

        file_out = io.BytesIO(b'')

        for chunk in response.iter_content(65_536):
            file_out.write(chunk)

        file_out.seek(0, io.SEEK_SET)
        return file_out

    def preview_stream(self):

        youtube_url = 'https://i.ytimg.com/vi/{}/maxresdefault.jpg'.format(self.video_id)

        response = requests.get(youtube_url, stream=True, timeout=5)

        if response.status_code == HTTPStatus.OK:
            return Youtube._binary_stream_from_response(response)

        elif response.status_code == HTTPStatus.NOT_FOUND:

            command = [
                'youtube-dl', '--dump-single-json', 'https://www.youtube.com/watch?v={}'.format(self.video_id)
            ]

            sp = subprocess.Popen(command,
                                  shell=False,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  universal_newlines=True)

            # Separate the output and error.
            # This is similar to Tuple where we store two values to two different variables
            out, err = sp.communicate()

            # Store the return code in rc variable
            return_code = sp.wait()

            if return_code == 0:
                json_data = json.loads(out)

                if "thumbnails" not in json_data:
                    return None

                if len(json_data['thumbnails']) == 0:
                    return None

                response = requests.get(json_data["thumbnails"][-1]['url'], stream=True)

                if response.status_code == HTTPStatus.OK:
                    return Youtube._binary_stream_from_response(response)

        return None


def factory(link: str):
    o = urllib.parse.urlparse(link)

    if o.netloc in ('www.youtube.com', 'youtube.com') and o.path == '/watch':
        return Youtube(link)

    return Link(link)
