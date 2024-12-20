# project/server/config.py

import os
import sys
from pathlib import Path

basedir = Path(__file__).absolute().parent.parent.parent
database_name = 'desktop'


def sqlite3_filename(postfix=''):
    filename = basedir / 'data' / (database_name + postfix + '.db')

    return 'sqlite:///' + str(filename)


class BaseConfig:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'my_precious')
    DEBUG = False
    BCRYPT_LOG_ROUNDS = 13
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    BCRYPT_LOG_ROUNDS = 10
    SQLALCHEMY_DATABASE_URI = sqlite3_filename('_development')

    SQLALCHEMY_ECHO = True
    # SQLALCHEMY_DATABASE_URI = 'mysql://development:Uf5aejeeliehah1cuch6ze6Aiba4IeZi@127.0.0.1/development_cms'

    STORAGES = [
        {
            'name': 'Documents',
            'description': 'Description for Documents',
            'fs_identifier': str(basedir / 'storages' / 'documents'),
        },
        {
            'name': 'Music',
            'description': 'Description for Music',
            'fs_identifier': str(basedir / 'storages' / 'music'),
        },
        {
            'name': 'Pictures',
            'description': 'Description for Pictures',
            'fs_identifier': str(basedir / 'storages' / 'pictures'),
        },
        {
            'name': 'Videos',
            'description': 'Description for Videos',
            'fs_identifier': str(basedir / 'storages' / 'videos'),
        },
    ]


class DevelopmentConfigFuzz(DevelopmentConfig):
    STORAGES = [
        {
            'name': 'txt',
            'description': 'These are my media',
            'fs_identifier': '/home/fuzz/git/git.home/media/',
        },
    ]


class TestingConfig(BaseConfig):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    SECRET_KEY = 'my_precious'
    BCRYPT_LOG_ROUNDS = 4
    SQLALCHEMY_DATABASE_URI = sqlite3_filename('_testing')
    PRESERVE_CONTEXT_ON_EXCEPTION = False


class ProductionConfig(BaseConfig):
    """Production configuration."""
    SECRET_KEY = b'#\x9b"zh\x833\xd0\x8e\xa05l*\x02\x88\xf5~&Jj\x024\x12\xb0'
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = sqlite3_filename('_productive')
