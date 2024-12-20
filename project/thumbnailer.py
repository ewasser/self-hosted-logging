#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

from PIL.Image import Resampling
from PIL import Image

from enum import IntEnum


class Season(IntEnum):
    CLASSIC = 1
    CENTERED = 2


class Thumbnailer:
    def __init__(self, mode: Season, size):
        self.mode = mode
        self.size = size

    def __repr__(self):
        return '({!r}, {!r})'.format(
            self.size,
            str(self.mode),
        )

    def thumbnail_image(self, image):
        if self.mode == Season.CLASSIC:
            image.thumbnail(self.size, Resampling.LANCZOS)
            return image
        elif self.mode == Season.CENTERED:
            image.thumbnail(self.size, Resampling.LANCZOS)

            thumbnail_size = image.size

            offset = (
                (self.size[0] // 2) - (thumbnail_size[0] // 2),
                (self.size[1] // 2) - (thumbnail_size[1] // 2),
            )

            transparent_thumbnail = Image.new("RGBA", self.size, (0, 0, 0, 0))
            transparent_thumbnail.paste(image, offset)

            return transparent_thumbnail

    # def combine(i1, i2):
    #         i1 = Image.open(i1)
    #
    #     i2 = Image.open(i2)
    #     x1, y1 = i1.size
    #     x2, y2 = i2.size
    #     x3 = x1 + x2
    #     y3 = y1 if y1 > y2 else y2
    #     if y1 > y2:
    #             y2 = (y1 - y2) // 2
    #      else:
    #         y2 = y1
    #     i3.paste(i1, (0, 0), i1)
    #     i3.paste(i2, (x1, y2), i2)
    #     return i3
    #  
    # i = combine("folder.png", "py.png")
    # i.save("folder.png", "PNG")
    # i

    def thumbnail(self, image=None, filename=None, file_input=None, file_output=None):

        if image:
            image = self.thumbnail_image(image)
            return image

        if filename:
            image = Image.open(filename)
            image = self.thumbnail_image(image)
            image.save(filename, image.format)

            return image

        if file_input and file_output:
            image = Image.open(file_input)
            image = self.thumbnail_image(image)
            image.save(file_output, image.format)
            return image

        raise ValueError("Unknown parameter combination")


def convert_file_list(thumbnailer: Thumbnailer, files):

    for infile in files:

        filename_in = Path(infile)
        filename_out = filename_in.with_suffix('.t.png')

        print("'{}'->'{}' {!r}".format(filename_in, filename_out, thumbnailer))

        thumbnailer.thumbnail(file_input=filename_in,
                              file_output=filename_out)


def get_thumbnail_size(cli_size_parameter: str):

    image_parameter = (128, 128)

    if cli_size_parameter:
        match = re.match(r'^(\d+)x(\d+)$', cli_size_parameter)
        image_parameter = (int(match.group(1)), int(match.group(2)))

    return image_parameter


def get_thumbnail_mode(cli_mode_parameter: str):

    if cli_mode_parameter == 'classic':
        return Season.CLASSIC

    if cli_mode_parameter == 'centered':
        return Season.CENTERED


def cli_entrypoint():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='display a square of a given number',
                        type=str)
    parser.add_argument('-o', '--output', help='display a square of a given number',
                        type=str)
    parser.add_argument('-s', '--size', help='display a square of a given number',
                        type=str, default='128x128')

    parser.add_argument('-m', '--mode', type=str, default='classic', choices=['classic', 'centered'])

    parser.add_argument('files', nargs='*')

    args = parser.parse_args()

    thumbnailer = Thumbnailer(
        mode=get_thumbnail_mode(args.mode),
        size=get_thumbnail_size(args.size)
    )

    if args.files:
        convert_file_list(thumbnailer, args.files)

    if args.input and args.output:
        print("'{}'->'{}' {!r}".format(args.input, args.output, thumbnailer))
        thumbnailer.thumbnail(
            file_input=args.input,
            file_output=args.output,
        )


if __name__ == "__main__":
    cli_entrypoint()
