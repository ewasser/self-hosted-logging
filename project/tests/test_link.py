# project/tests/test_link.py

import pytest
from diskcache import Cache

from project.server.link import factory, Youtube, LinkType


@pytest.fixture
def cache():
    cache = Cache()
    return cache


def test_link(cache):
    l = factory('https://www.youtube.com/watch?v=UOeNBCezeCo')
    assert isinstance(l, Youtube)
    assert l.kind == LinkType.VIDEO
    assert l.video_id == 'UOeNBCezeCo'

    h = l.thumbnail_image_stream(cache)

