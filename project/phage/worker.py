#!/usr/bin/env python3

import asyncio
import collections
import io
import os
import json
import shutil
import tempfile
import time
from dataclasses import dataclass


from pathlib import Path
from typing import Optional, Any

import phage.client

a = collections.UserDict

#
#   basename = foobar
#   rootdir
#   +--
#   +-- .local/bin/your-name.py
#   +-- .local/config/$basename/global.yml (file)
#   +-- .local/config/$basename/payload.yml (file)
#   +-- .local/state/$basename
#   +-- .local/state/$basename/next_step.yml
#   +-- .local/state/$basename/outputs (directory)
#   +-- .local/state/$basename/outputs/output.1.yml (file)
#


class Filesystem:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def create(self, entries):
        for entry in entries:
            entry.create(self.root_dir / entry.name)

    def __truediv__(self, p: Path):
        return Filesystem(self.root_dir / p)


@dataclass
class Directory:
    name: Path

    def create(self, target: Path):
        target.mkdir(parents=True, exist_ok=True)


@dataclass
class File:
    name: Path
    handle: Optional[Any] = None
    content: Optional[str] = None
    data: Optional[dict|list] = None
    mode: Optional[int] = None

    def create(self, target: Path):

        BUFFER_SIZE: int = 65_536

        if self.handle is not None:
            with io.open(str(target), 'w+') as destination_handle:
                for chunk in iter(lambda: self.handle.read(BUFFER_SIZE), ''):
                    destination_handle.write(chunk)

        elif self.data is not None:
            with io.open(str(target), 'w', encoding='utf-8') as destination_handle:
                if target.suffix in ['.yaml', '.yml']:
                    json.dump(self.data, destination_handle, indent=4)
                elif target.suffix == '.json':
                    json.dump(self.data, destination_handle, indent=4)

        elif self.content is not None:
            with io.open(str(target), 'w', encoding='utf-8') as destination_handle:
                destination_handle.write(self.content)
        else:
            raise ValueError()

        if self.mode is not None:
            target.chmod(self.mode)


@dataclass
class Proc:
    start_time: float
    finish_time: float
    duration: float
    return_code: int
    output: str


class Configuration:
    def __init__(self, root_path: Path, c: dict):
        self.configuration=c['configuration']
        self.flow=c['flow']
        self.payload=c['payload']
        self.node=c['node']

    def root_dir(self) -> Path:
        return Path(self.configuration['root_dir'])

    def local_directory(self, append: Path = None) -> Path:
        p = self.root_dir / '.local'

        if append is not None:
            p = p / append

        return p


class Worker:
    def __init__(self, script: Path, name: str, root_path: Path = None):
        self.root_path = root_path
        self.name = name
        self.script = script
        self.cleanup_root_path = False

        if self.root_path is None:
            self.root_path = Path(tempfile.TemporaryDirectory().name)
            self.cleanup_root_path = True

        self.filesystem = Filesystem(self.root_path)

        self.work_data = None

    def create(self, modules=None, configurations=None, streams=None, state=None) -> None:

        modules = modules or []
        configurations = configurations or {}
        streams = streams or {}

        python_directory = Path('lib/python')

        filesystem = self.filesystem / '.local'
        filesystem.create([
            Directory(Path('bin')),
            Directory(Path('config')),
            Directory(Path('config') / self.name),
            Directory(python_directory),
            Directory(Path('state')),
            Directory(Path('state') / self.name),

            #   +-- .local/bin/your-name.py
            #   +-- .local/config/$basename/global.yml (file)
            #   +-- .local/config/$basename/payload.yml (file)
            File(
                name=Path('bin') / self.script.name,
                handle=io.open(self.script),
                mode=0o755,
            ),
            File(
                name=Path('lib/python') / 'Testi.py',
                content="print(\"Foobar-From-Import\")\n",
            )
        ])

        if state:
            filesystem.create([
                File(
                    name=filesystem.root_dir / 'state' / self.name / 'state.json',
                    data=state,
                    mode=0o644,
                ),
            ])
                              #        self.work_data = phage.client.WorkData.create(
#            p=filesystem.root_dir / 'state' / self.name / 'state.json',
#            configurations=configurations,
#            streams=streams,
#        )

        #
        for module in modules:
            source_filename = Path(module.__file__)
            destination_filename = Path(module.__package__) / source_filename.name

            with io.open(str(source_filename), 'r', encoding='utf-8') as source_handle:
                filesystem.create([
                    Directory(python_directory / destination_filename.parent),
                    File(
                        name=python_directory / destination_filename,
                        handle=source_handle,
                    ),
                ])

    async def run(self):
        cmd = str(Path('.local') / 'bin' / self.script.name)

        output = None

        with tempfile.TemporaryFile(mode='w+', encoding='utf8') as h:

            proc = await asyncio.create_subprocess_exec(
                cmd,
                stdout=h,
                stderr=h,
                cwd=str(self.root_path),
                env={
                    'PYTHONPATH': str(Path(self.root_path/'.local/lib/python')),
                  # 'PHAGE_NODE_CONFIGURATION': 'phage_node_configuration.yml'
                }
            )

            start_time = time.time()
            await proc.communicate()
            finish_time = time.time()

            h.seek(0, os.SEEK_SET)
            output = ''.join(h)

        if self.cleanup_root_path:
            shutil.rmtree(self.root_path)

        return Proc(
            start_time=start_time,
            finish_time=finish_time,
            duration=finish_time-start_time,
            return_code=proc.returncode,
            output=output,
        )

# os.environ["TEST"] = "/foobar"
# asyncio.run(run('./foo.py'))
#
#
# class Run:
#     def __init__(self, root_dir: Path, global_vars: dict, payload: dict):
#         self.root_dir = root_dir
#
#     def filename(self, p: Path) -> Path:
#         assert not p.is_absolute()
#         return self.root_dir / p.name
#
#     async def create_env(self):
#         await aiofiles.os.mkdir(self.filename() / Path('lib'))
#
#         checksum_name = 'sha256'
#         block_size = 65536
#         h = hashlib.new(checksum_name)
#         with open(p.full_name, mode='rb') as f:
#             for block in iter(lambda: f.read(block_size), b''):
#                 h.update(block)
#
#
# from jinja2 import Template
#
# t = Template('Hello, {{ name }}!')
# print(t.render(name='John Doe'))
#
# # Output:
# # 'Hello, John Doe!'
#
#
#
# # # SuperFastPython.com
# # # example of asynchronous generator with async for loop
# #
# # # define an asynchronous generator
# # async def async_generator():
# #     # normal loop
# #     for i in range(10):
# #         # block to simulate doing work
# #         await asyncio.sleep(1)
# #         # yield the result
# #         yield i
# #
# # # main coroutine
# # async def main():
# #     # loop over async generator with async for loop
# #     async for item in async_generator():
# #         print(item)
#
# # execute the asyncio program
# if __name__ == '__main__':
#     asyncio.run(main())
#
