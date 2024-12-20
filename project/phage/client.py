#!/usr/bin/env python3
import functools
import itertools
import collections
import os
import re
import tempfile
from pathlib import Path
from typing import Union, Optional, List, Dict

import sys
import io
import json


instance = None
payload = None
workload = None
output = None


def from_configuration(configuration: dict):
    return SingletonClass(configuration)


def read_configurations(directory: Path, names: List[str]):
    d = {}

    for name in names:
        full_path = directory / (name + '.json')
        print(full_path)

        if full_path.exists():
            with io.open(full_path, encoding='utf8') as h:
                d[name] = json.load(h)

    return d


class SingletonClass:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.state = {
            'payload': {
                'aaa': True
            }
        }
        self.state_filename = self.root_dir / '.local/state/phage/state.json'

        with io.open(self.state_filename, mode='r', encoding='utf8') as h:
            self.state = json.load(h)

    def write_state(self):
        with io.open(self.state_filename, mode='w+', encoding='utf8') as h:
            json.dump(self.state, h)

    #   Shortcut calls
    def payload(self):
        return self.state['payload']

    def workload(self):
        return self.state['workload']

    def node(self):
        return self.state['node']

    def output(self, output: Union[dict, list], name=None):
        if name is None:
            name = self.state['node']['outputs'][0]

        if name not in self.state['node']['outputs']:
            raise ValueError()

        if name not in self.state['outcome']:
            self.state['outcome'][name] = []

        self.state['outcome'][name].append(output)

        self.write_state()
    #   End of shortcut calls

    def _write_outcome(self, output: Union[dict, list]):
        self.current_outcome += 1
        filename = self.root_dir / '.local/state/phage/outputs/outcome.{}.json'.format(self.current_outcome)

        with open(filename, 'w+') as stream:
            json.dump(output, stream, indent=2)

    def _write_next_node(self, name):
        filename = self.root_dir / '.local/state/phage/next_node.json'.format(self.current_outcome)

        with open(filename, 'w+') as stream:
            r = {
                'next_node': name
            }
            json.dump(r, stream, indent=2)

    def outcome(self, output: Optional[Union[dict, list]] = None, name: Optional[str] = None):
        if output is not None:
            self._write_outcome(output)

        if name is not None:
            self._write_next_node(name)


# class State:
#     def __init__(self, path: Path):
#         self.data = data
#         with io.file(path, 'r', encoding='utf8') as h:
#             self.data = json.load(h)
#
#         self.changed = False
#
#     @staticmethod
#     def
#         self.data = {
#             'vars': {},
#             'streams': {
#             }
#         }
#
#     def save(self, force: bool = False):
#         if self.changed or force:
#
#             self.changed = False
#
#
#
#     def read_stream(self):
#
#     def write_stream(self)
#
#     def
#
#     def save(self):


class ChunkData:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.exhausted = False

        self.last_used_number = 0

        if not self.data_dir.exists():
            self.data_dir.mkdir()

    def reset(self, delete_data=False):
        #   Removes all data
        if delete_data:
            for p in self.data_dir.glob('*.json'):
                p.unlink()

        self.last_used_number = 0
        self.exhausted = False

    @staticmethod
    def generate_path(data_dir, number):
        return data_dir / '{}.json'.format(number)

    def read_chunk(self):
        if self.exhausted:
            return

        #   We're checking if the next file is there.
        filename = ChunkData.generate_path(self.data_dir, self.last_used_number+1)

        if not filename.exists():
            self.exhausted = True
            return

        #   And if it exists, we increase the internal logical number.
        self.last_used_number += 1

        with io.open(filename, 'r', encoding='utf8') as h:
            return json.load(h)

    def read_chunks(self):
        while True:
            chunk = self.read_chunk()
            if chunk is None:
                return

            yield chunk

    def write_chunk(self, data: Union[dict, list]):
        self.last_used_number += 1

        filename = ChunkData.generate_path(self.data_dir, self.last_used_number)

        with io.open(filename, 'w+', encoding='utf8') as h:
            json.dump(data, h)

    def write_chunks(self, data: List[Union[dict, list]]):
        for d in data:
            self.write_chunk(d)


class ChunkReadData(ChunkData):
    def __init__(self, data_dir, data=None):
        super().__init__(data_dir, data)

        if data:
            for d in data:
                self.write_chunk(d)
                self.reset()


class ChunkWriteData(ChunkData):
    def __init__(self, data_dir, data):
        super().__init__(data_dir, data)

        if data:
            for d in data:
                self.write_chunk(d)


class Chunks(collections.UserDict):

    RE_VALID_NAME = re.compile(r"^[a-z_][\da-z_]{0,64}", re.IGNORECASE)

    @staticmethod
    def _write_data(chunk, data):
        for d in data:
            chunk.write_chunk(d)

    @staticmethod
    def asasd(data):
        if isinstance(data, list):
            for name in data:
                yield name, []
        elif isinstance(data, dict):
            for name, data in data.items():
                yield name, data

    def __init__(self, root_data: Path = None, read_names: Union[List, Dict] = None,
                 write_names: Union[List, Dict] = None):

        super().__init__()

        if isinstance(root_data, str):
            root_data = Path(root_data)

        self.root_data = root_data
        self.temporary_directory = None

        if self.root_data is None:
            self.temporary_directory = tempfile.TemporaryDirectory()
            self.root_data = Path(self.temporary_directory.name)

        self.read_names = read_names or []
        self.write_names = write_names or []

        for name in itertools.chain(self.read_names, self.write_names):
            m = Chunks.RE_VALID_NAME.match(name)
            if not m:
                raise KeyError(name)

        for name, data in Chunks.asasd(read_names):
            self.data[name] = ChunkData(self.root_data / name)
            self.data[name].write_chunks(data)
            self.data[name].reset()

        for name, data in Chunks.asasd(write_names):
            self.data[name] = ChunkData(self.root_data / name)
            self.data[name].write_chunks(data)

    def cleanup(self):
        if self.temporary_directory is not None:
            self.temporary_directory.cleanup()


class WorkDataConfigurationProxy:
    def __init__(self, work_data, data: dict = None):
        self.work_data = work_data
        self.data = data or {}

    def update(self, name: str, data: dict):
        self.data.update(data)
        self.work_data.save()


class WorkDataStreamProxy:
    def __init__(self, work_data, data: list = None) :
        self.work_data = work_data
        self.data = data or []

    def append(self, item):
        self.data.append(item)
        self.work_data.save()


class WorkData:
    """
    {
        #   configurations
        'configurations': {
            'test': {},
        },
        #   streams
        'streams': {
            'name': [],
        },
    }
    """
    @staticmethod
    def create(p: Path, configurations: dict, streams: dict):
        work_data = WorkData(p, configurations, streams)
        work_data.save()

    def __init__(self, p: Path, configurations: dict, streams: dict):
        self.json_path = p
        self.configurations = self.init_configurations(configurations)
        self.streams = self.init_streams(streams)

    def init_configurations(self, data):
        if isinstance(data, list):
            return dict(
                list(
                    map(
                        lambda name: (name, WorkDataConfigurationProxy(self), data), data)))
        elif isinstance(data, dict):
            return dict(
                list(
                    map(
                        lambda name: (name, WorkDataConfigurationProxy(self, data[name])), data.keys())))

        raise ValueError()

    def init_streams(self, data):
        if isinstance(data, list):
            return dict(
                list(
                    map(
                        lambda name: (name, WorkDataStreamProxy(self)), data)))
        elif isinstance(data, dict):
            return dict(
                list(
                    map(
                        lambda name: (name, WorkDataStreamProxy(self, data[name])), data.keys())))

        raise ValueError()

    def load(self):
        with io.open(self.json_path, 'r', encoding='utf8') as h:
            data = json.load(h)

            self.configurations = self.init_configurations(data['configurations'])
            self.streams = self.init_streams(data['streams'])

    def save(self):
        data = {
            'configurations':
                dict(
                    list(
                        map(
                            lambda x: (x, self.configurations[x].data), self.configurations.keys()))),
            'streams':
                dict(
                    list(
                        map(
                            lambda x: (x, self.streams[x].data), self.streams.keys()))),
        }
        with io.open(self.json_path, 'w+', encoding='utf8') as h:
            json.dump(data, h)

    def configuration_proxy(self, name: str):
        return self.configurations[name]

    def stream_proxy(self, name: str):
        pass
        #
        # return self.streams[name]
        # def sadasdasd(data: Union[dict, list], name=None)
        #     return self.streams[name]


# def ss():
#     root_dir = Path(os.environ['PHAGE_NODE_CONFIGURATION']) \
#         if 'PHAGE_NODE_CONFIGURATION' in os.environ else Path.cwd()
#
#     print(root_dir)
#
#     with open(root_dir / '.config/globals.yml', 'r') as stream:
#         all = yaml.load(stream, Loader=yaml.SafeLoader)
#
#     print("AAA")
#
#     a = SingletonClass(
#         root_dir=root_dir,
#         config=all,
#         flow=all['flow'],
#         payload=all['payload'],
#         node=all['node'],
#     )
#     print(a)
#     print(dir(a))
#     return a


# phage = ss()
#
# payload = phage.payload
# #
# node = phage.node


#
# outcomes = ALL['outcomes']
#
# class SingletonClass:
#     instance = None
#
#     def __new__(cls):
#         if not hasattr(cls, 'instance'):
#             cls.instance = super(SingletonClass, cls).__new__(cls)
#
#         return cls.instance
#
# singleton = SingletonClass()
# new_singleton = SingletonClass()
#
# print(singleton is new_singleton)
#
# singleton.singl_variable = "Singleton Variable"
# print(new_singleton.singl_variable)

def from_env():
    global instance, payload, workload, node, output

    if instance is not None:
        return instance

    current_module = sys.modules[__name__]

    root_dir = Path(os.environ['PHAGE_NODE_CONFIGURATION']) \
        if 'PHAGE_NODE_CONFIGURATION' in os.environ else Path.cwd()

    #   Define our main object…
    instance = SingletonClass(root_dir=root_dir)
    #   …and define some shortcuts.
    payload = functools.partial(instance.payload)
    workload = functools.partial(instance.workload)
    node = functools.partial(instance.node)
    output = functools.partial(instance.output)


def debug_information():
    global instance
    print('INSTANCE:')
    print("* root_dir ... : {}".format(instance.root_dir))
    print()


