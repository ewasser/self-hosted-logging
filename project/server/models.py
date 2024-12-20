# project/server/models.py

import datetime
import json
from pathlib import Path

import jwt
from flask import current_app

# from project.server import startup, models, bcrypt
from sqlalchemy import ForeignKey

from project.server import crypt
from project.server.database import db
from sqlalchemy.orm import relationship

DEFAULT_ALGORITHM = 'HS256'


def convert_json_data(s: dict, converter):

    for name, field_names in converter.items():
        if name == 'datetime':
            for field_name in field_names:
                if s[field_name] is None:
                    s[field_name + '_human'] = None
                    s[field_name] = None
                else:
                    s[field_name + '_human'] = s[field_name].strftime('%Y-%m-%d %H:%M:%S')
                    s[field_name] = s[field_name].strftime('%s')

    return s


class User(db.Model):
    """ User Model for storing user related details """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    registered_on = db.Column(db.DateTime, nullable=False)
    admin = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, email, password, admin=False):
        self.email = email
        self.password = crypt.bcrypt.generate_password_hash(
            password,
            current_app.config.get('BCRYPT_LOG_ROUNDS')
        ).decode()
        self.registered_on = datetime.datetime.now()
        self.admin = admin

    @staticmethod
    def encode_auth_token(user_id: str, period=None):
        """
        Generates the Auth Token
        :return: string
        """
        if period is None:
            period = datetime.timedelta(days=1, seconds=0)

        try:
            payload = {
                'exp': datetime.datetime.utcnow() + period,
                'iat': datetime.datetime.utcnow(),
                'sub': user_id
            }
            return jwt.encode(
                payload,
                current_app.config.get('SECRET_KEY'),
                algorithm=DEFAULT_ALGORITHM,
            )
        except Exception as e:
            return e

    @staticmethod
    def decode_auth_token(auth_token):
        """
        Validates the auth token
        :param auth_token:
        :return: integer|string
        """
        try:
            payload = jwt.decode(auth_token, current_app.config.get('SECRET_KEY'), algorithms=DEFAULT_ALGORITHM)
            is_blacklisted_token = BlacklistToken.check_blacklist(auth_token)
            if is_blacklisted_token:
                raise ValueError('Token blacklisted. Please log in again.')

            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError('Signature expired. Please log in again.')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token. Please log in again.')


class Archive(db.Model):

    __tablename__ = "archive"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source = db.Column(db.Text(), unique=False, nullable=False)
    name = db.Column(db.Text(), unique=False, nullable=False)


class BlacklistToken(db.Model):
    """
    Token Model for storing JWT tokens
    """
    __tablename__ = 'blacklist_tokens'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token = db.Column(db.String(500), unique=True, nullable=False)
    blacklisted_on = db.Column(db.DateTime, nullable=False)

    def __init__(self, token):
        self.token = token
        self.blacklisted_on = datetime.datetime.now()

    def __repr__(self):
        return '<id: token: {}'.format(self.token)

    @staticmethod
    def check_blacklist(auth_token):
        # check whether auth token has been blacklisted
        res = BlacklistToken.query.filter_by(token=str(auth_token)).first()
        if res:
            return True
        else:
            return False


class Hit(db.Model):
    """
    Token Model for storing our hits brought by the external
    REST API.
    """
    __tablename__ = 'hits'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    url = db.Column(db.String(512), unique=False, nullable=False)
    mtime = db.Column(db.DateTime, unique=False, nullable=False)
    title = db.Column(db.String(512), unique=False, nullable=False)

    download = db.Column(db.Boolean, nullable=False, default=False)
    deleted = db.Column(db.Boolean, nullable=False, default=False)

    visited = db.Column(db.Integer, unique=False, nullable=False)

    order_id = db.Column(db.Integer, ForeignKey('orders.id'))
    order = relationship("Order", back_populates="hits")
    # order = relationship("Order", back_populates="hit")


class YoutubeVideo(db.Model):

    """ User Model for storing user related details """
    __tablename__ = "youtube_videos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(4096), unique=True, nullable=False)
    registered_on = db.Column(db.DateTime, nullable=False)

    title = db.Column(db.String(255), nullable=False)
    youtube_id = db.Column(db.String(11), unique=True, nullable=False)
    playlist_id = db.Column(db.String(255), nullable=True)
    playlist_index = db.Column(db.Integer(), nullable=True)


class Order(db.Model):

    """ User Model for storing orders for a mini pub/sub service """
    __tablename__ = "orders"

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    registered_on = db.Column(db.DateTime, nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    finish_time = db.Column(db.DateTime, nullable=True)
    title = db.Column(db.Text(), nullable=False)

    channel = db.Column(db.String(512), nullable=False)
    payload = db.Column(db.Text(), nullable=False)

    #   new         =   Order is new, do anything you like
    #   working     =   A `Worker` is working on this order
    #   error       =   A `Worker` stopped with an error
    #   finished    =   A `Worker` has successfully finished it's work
    status = db.Column(db.String(256), nullable=False)

    uuid = db.Column(db.String(36), nullable=True)

    log_lines = relationship("OrderLog")
    worker = relationship("Worker")
    # hit = relationship("Hit")
    hits = relationship("Hit", back_populates="order")

    def as_json(self):

        return convert_json_data({
            'id': self.id,
            'registered_on': self.registered_on,
            'title': self.title,

            'channel': self.channel,
            'payload': json.loads(self.payload),
            'status': self.status,

            'uuid': self.uuid,
        }, {
            'datetime': ['registered_on'],
        })

    def log(self, category, line):
        return OrderLog(
            registered_on=datetime.datetime.now(),
            order_id=self.id,
            category=category,
            line=line,
        )


class OrderLog(db.Model):

    """ User Model for storing log lines  """
    __tablename__ = "order_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    registered_on = db.Column(db.DateTime, nullable=False)

    order_id = db.Column(db.Integer, ForeignKey('orders.id'))

    category = db.Column(db.String(512), nullable=False)
    line = db.Column(db.Text(), nullable=False)

    order = relationship("Order", back_populates="log_lines")


class Worker(db.Model):

    __tablename__ = "worker"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, ForeignKey('orders.id'))
    start_time = db.Column(db.DateTime, nullable=False)

    finish_time = db.Column(db.DateTime, nullable=True)
    uuid = db.Column(db.String(36), nullable=True)
    name = db.Column(db.Text(), nullable=True)

    ip = db.Column(db.Text(), nullable=True)

    output = db.Column(db.Text(), nullable=True)
    exit_code = db.Column(db.Integer(), nullable=True)

    order = relationship("Order", back_populates="worker")

    def as_json(self):

        return convert_json_data({
            'id': self.id,
            'order_id': self.order_id,
            'start_time': self.start_time,

            'finish_time': self.finish_time,
            'name': self.name,
            'ip': self.ip,

            'output': self.output,
            'exit_code': self.exit_code,
        }, {
            'datetime': ['start_time',
                         'finish_time'
                         ],
        })


class MyUser:

    def __init__(self, user_in_database):
        self.id = None
        if user_in_database:
            self.id = user_in_database.id

    @property
    def is_authenticated(self):
        """
        This property should return True if the user is authenticated, i.e. they have provided valid credentials.
         (Only authenticated users will fulfill the criteria of login_required.)
        """
        if self.id and self.id > 0:
            return True

        return False

    @property
    def is_active(self):
        """
        This property should return True if this is an active user - in addition to being authenticated,
         they also have activated their account, not been suspended, or any condition your application
          has for rejecting an account. Inactive accounts may not log in (without being forced of course).
        """
        return True

    @property
    def is_anonymous(self):
        """
        This property should return True if this is an anonymous user. (Actual users should return False instead.)
        """
        if self.id is None:
            return True

        return False

    def get_id(self):
        """
        This method must return a unicode that uniquely identifies this user, and can be used to load the
        user from the user_loader callback. Note that this must be a unicode - if the ID is natively an
        int or some other type, you will need to convert it to unicode.
        """
        return str(self.id)


from dataclasses import dataclass


@dataclass
class DiaryEntry:
    name: str
    path_extender: str
    node: str


class Diary:
    def __init__(self, path_extender):
        self.collection_dir = Path('/tmp/diary')
        self.path_extender = Path(path_extender)

    def collection(self):

        collection_dir = self.collection_dir / self.path_extender

        for d in collection_dir.iterdir():

            node = 'directory'
            if d.is_file():
                node = 'file'

            entry = DiaryEntry(
                name=d.name,
                path_extender=self.path_extender / d.name,
                node=node,
            )
            yield entry

    def filename(self):
        return self.collection_dir / self.path_extender

    @staticmethod
    def model(path_extender):
        return Diary(
            path_extender='.',
        )
        if year is not None and month is None:
            return Diary(
                name='month',
                path_extender=str(year),
            )
        if year is not None and month is not None:
            return Diary(
                name='days',
                path_extender=str(year)/str(month),
            )
        raise SyntaxError()


"""
V2:

We have processes and we've flows and we've rules.

A processes are some steps, that we need. Let's show some examples:

--
  name:
  begin:
  end:
  




"""
