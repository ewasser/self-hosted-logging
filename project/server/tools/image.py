#!/usr/bin/env python

from pathlib import Path

from subprocess import Popen, PIPE


def create_thumbnail(resolution, filename_image: Path, thumbnail_image: Path):

    process = Popen([
        'thumbnailer.py',
        '-s', '{}x{}'.format(resolution[0], resolution[1]),
        '-i', str(filename_image),
        '-o', str(thumbnail_image),
        ])

    process.communicate()
