import collections
import copy
import datetime
import io
import json
import logging
import os
import shlex
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import requests
import yaml
from jinja2 import Template


class Loop:
    def __init__(self, loader, worker, saver):
        self.loader = loader
        self.worker = worker
        self.saver = saver

        self.timeout = 5

    def execute(self):

        retry_interval = 10

        while True:

            time_before_loader = time.time()
            ctx = self.loader()
            time_after_loader = time.time()

            if ctx is None:
                if (time_after_loader - time_before_loader) < 0.5:
                    logging.info("Loader returned nothing very fast, retrying after sleeping for {} seconds...".
                                 format(retry_interval))
                    time.sleep(retry_interval)
                continue

            self.worker(ctx)

            self.saver(ctx)


def templating(template: str, template_parameter):
    template = Template(template)

    return template.render(**template_parameter)


def normalize_script(s):
    #   Convert my list of lines into a big ascii thing.
    if isinstance(s, list):
        s = "".join(map(lambda x: x + "\n", s))

    #   And make sure that the last line always with an '\n'
    if len(s) >= 1 and s[-1] != "\n":
        s += "\n"

    return s


class Environment:
    def __init__(self, root_dir: Path, name):
        """
        / self.root_dir
        +
        +- run.sh
        +- run.meta.yaml
        """
        self.root_dir = Path(root_dir)
        if not self.root_dir.exists():
            raise FileNotFoundError("My Environment 'root_dir' '{}' was not found".format(self.root_dir))
        if not self.root_dir.is_absolute():
            self.root_dir = self.root_dir.absolute()

        self.template_name = name

        self.guid = None
        self.timestamp = None
        self.name = None
        self.base_dir = None
        self.env = None

    def execute(self):

        self.guid = uuid.uuid4()
        self.timestamp = datetime.datetime.now()

        self.name = templating(self.template_name, {
            'timestamp': self.timestamp.strftime('%Y-%m-%d_%H%M%S'),
            'guid': str(self.guid),
        })

        self.base_dir = self.root_dir / self.name

        self.env = {
            'name': self.name,
            'timestamp': self.timestamp.strftime('%Y-%m-%d_%H%M%S'),
            'guid': str(self.guid),
            'path': {
                'root': str(self.base_dir),
            },
            'files': {
                'name': str(self.base_dir / 'run'),
                'work': str(self.base_dir / 'run.work.yaml'),
                'meta': str(self.base_dir / 'run.meta.yaml'),
                'worker': str(self.base_dir / 'run.sh'),
                'result': str(self.base_dir / 'run.result'),
            }
        }

        self.base_dir.mkdir()

        with io.open(self.env['files']['meta'], "w+", encoding='utf8') as f:
            yaml.dump(self.env, f)


class Worker:
    def __init__(self):
        self.output = None
        self.exit_code = None

        self._diagnostic_text = None

    def execute(self, payload, parameter):
        json_work_filename = parameter['env']['files']['work']

        with io.open(json_work_filename, 'w+') as f:
            yaml.dump(payload, f)

        with io.open(parameter['env']['files']['result'], mode='a+', encoding='utf8') as f:
            sp = subprocess.Popen(parameter['env']['files']['worker'],
                                  shell=True,
                                  stdout=f,
                                  stderr=f,
                                  encoding='utf8',
                                  universal_newlines=True)

            sp.communicate()
            rc = sp.wait()

            f.seek(0, os.SEEK_SET)
            self.output = ''.join(f.readlines())
            self.exit_code = rc

        print(self.diagnostic_text)

        return rc == 0

    @property
    def diagnostic_text(self):

        if self._diagnostic_text is not None:
            return self._diagnostic_text

        f = io.StringIO()
        f.write(">>> CALL rc = {} / output = {} lines >>>\n\n".format(
            self.exit_code,
            self.output.count("\n"),
        ))

        f.write(">>> OUTPUT >>>\n\n")
        f.write(self.output)
        f.write("\n")

        self._diagnostic_text = f.getvalue()

        return self._diagnostic_text

    @staticmethod
    def _normalize_output(s: str):
        if len(s) >= 1 and s[-1] != "\n":
            s += "\n"

        while len(s) >= 2 and s[-2:] == "\n\n":
            s = s[:-1]

        return s


def load_work_from_url(url, auth_token=None, payload=None):
    headers = {}
    if auth_token:
        headers['Authorization'] = 'Bearer {auth_token}'.format(auth_token=auth_token)

    r = requests.get(url, headers=headers, timeout=5, json=payload)

    return r.json()


def load_work_from_file(filename):
    with io.open(filename, 'r') as f:
        return yaml.load(f.read(), Loader=yaml.SafeLoader)


def load_work(url, load_local_files=False, auth_token=None, payload=None):
    if load_local_files and len(url) >= 1 and url[0] == '@':
        return load_work_from_file(url[1:])
    else:
        return load_work_from_url(url, auth_token, payload)


class Work(collections.UserDict):
    def __init__(self, data=None, meta=None):
        super().__init__(dict=data)
        self.meta = meta


class Script:
    def __init__(self, init_script, command_line, command_script):
        self.init_script = init_script
        self.command_line = command_line
        self.command_script = command_script
        self.env = None

        if (self.command_line is None and self.command_script is None) or \
                (self.command_line is not None and self.command_script is not None):
            raise ValueError()

        if isinstance(self.init_script, list):
            self.init_script = normalize_script(self.init_script)

        if isinstance(self.command_script, list):
            self.command_script = normalize_script(self.command_script)

    def execute(self, parameter):
        parameter = copy.copy(parameter)

        mode = 'command-line'

        if self.command_script:
            mode = 'command-script'

        self.env = {
            'mode': mode,
        }

        parameter['script'] = self.env

        basic_template = self.init_script

        if mode == 'command-line':
            basic_template += ' '.join(
                map(lambda s1: shlex.quote(s1),
                    map(lambda s2: templating(s2, parameter),
                        self.command_line))) + "\n"
        else:
            basic_template += self.command_script

        return templating(basic_template, parameter)
