# project/server/__init__.py

import datetime
import io
import logging
import os
import os.path
import pprint
import re
import unittest
from pathlib import Path

import bcrypt
import click
from flask import Flask, redirect, url_for
from flask.cli import AppGroup
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_restful import Api
from tabulate import tabulate

from project.diary import diary_blueprint
from project.gallery import gallery_blueprint
from project.hits import hits_blueprint
from project.markdown import markdown_blueprint
from project.order import order_blueprint
from project.server.crypt import bcrypt
from project.server.database import db
from project.server.models import User, MyUser, Hit
from project.server.tools.cache import cache
from project.storage import storage_blueprint
from project.user import user_blueprint
from project.v1.order import REST_Order_POST, REST_Order_GET, \
    REST_Orders_GET, REST_Order_Worker_Reserve
from project.v1.result import REST_Result
from project.youtube import youtube_blueprint
from project.testing import testing_blueprint

logger = logging.getLogger()


def root():
    return redirect(url_for("user.login"))


def cli_db_import(filename):

    with io.open(filename) as f:
        for line in f.readlines():
            line = line.rstrip("\n")

            data = line.split("\t")

            click.echo(data)

            youtube_hit = Hit(
                url=data[0],
                mtime=datetime.datetime.fromtimestamp(int(data[1])/1000),
                title=data[2],
            )
            db.session.add(youtube_hit)

    db.session.commit()


def install_decorator_for_load_user(app, login_manager):
    @login_manager.user_loader
    def load_user(user_id):
        app.logger.debug('load_user({})'.format(user_id))

        user_in_database = db.session.query(User).filter(User.id == int(user_id)).one_or_none()

        user = MyUser(user_in_database)

        return user


def install_decorator_for_request_loader(app, login_manager):
    @login_manager.request_loader
    def load_user_from_request(r):
        authorization_header = r.headers.get('Authorization', None)
        app.logger.debug('Authorization = {}'.format(authorization_header))
        if authorization_header is None:
            return None

        m = re.search(r'^Bearer (\S+)$', authorization_header)
        if not m:
            return None

        try:
            payload = User.decode_auth_token(m.group(1))
            logger.debug(payload)
            user_id = payload['sub']
        except ValueError as e:
            return None

        user_in_database = db.session.query(User).filter(User.id == int(user_id)).one_or_none()
        logger.debug('user = {}'.format(user_in_database))
        if not user_in_database:
            return None

        return MyUser(user_in_database)


def define_appgroup_data(app):
    data_cli = AppGroup('data', help='Modifies your SQL data (please be careful)')

    @data_cli.command('import')
    @click.argument('filename')
    def database_import(filename):
        """Imports the given filename into your table `hit`"""
        cli_db_import(filename)

    app.cli.add_command(data_cli)


def define_appgroup_token(app):
    token_cli = AppGroup('token', help='modifies the tokens in the database')

    @token_cli.command('create')
    @click.argument("email")
    def token_create(email):
        """Create a token with the given name and time valid period of 10 years."""
        user = db.session.query(User).where(User.email == email).one_or_none()

        if not user:
            click.secho("Can't find your user '{}'!".format(email), fg="red")
            return

        validation_period = datetime.timedelta(days=10*365)

        auth_token = user.encode_auth_token(user.id,
                                            period=validation_period)

        click.secho("Created token for user '{}' with a duration of {}: Bearer {}".format(email, validation_period, auth_token), fg='green')

    @token_cli.command('check')
    @click.argument("token")
    def token_check(token):
        """Checks the given token against validity"""

        try:
            payload = User.decode_auth_token(token)

            print("Token valid ..... : {}".format('yes'))
            print("User ID ......... : {}".format(payload['sub']))
            print("Creation time ... : {}".format(datetime.datetime.fromtimestamp(payload['iat'])))
            print("Expire time ..... : {}".format(datetime.datetime.fromtimestamp(payload['exp'])))

        except Exception as e:
            print(str(e))
            return

    app.cli.add_command(token_cli)


def define_appgroup_config(app):

    config_cli = AppGroup('config', help='prints the current configuration')

    @config_cli.command('dump')
    def config_dump():
        """Dumps your configuration with pprint.pformat()"""
        # click.echo(app.config)
        click.echo(pprint.pformat(app.config))

    app.cli.add_command(config_cli)


def define_appgroup_user(app):

    user_cli = AppGroup('user', help='asda')

    @user_cli.command('list')
    def user_list():
        """This is an example dump command."""

        rows = []

        for user in User.query.all():
            rows.append([
                user.id,
                user.email,
                user.registered_on,
                user.admin
            ])

        if len(rows) >= 1:
            print(tabulate(rows, tablefmt="plain"))
        return

    @user_cli.command('create')
    @click.option('--admin', default=False, is_flag=True, help='Admin User Account')
    @click.argument("name")
    def user_create(admin, name):
        """This is an example dump command."""

        validation_period = datetime.timedelta(days=10*365)

        user = User(email=name, password='not-yet-supported')
        db.session.add(user)
        db.session.commit()

        auth_token = user.encode_auth_token(user.id,
                                            period=validation_period)

        click.echo("Created user {} with {}, auth_token = {}".format(name, validation_period, auth_token))

    app.cli.add_command(user_cli)
    #


def create_app(testing=False):
    app = Flask(__name__)

    app_settings = os.environ.get('APP_SETTINGS', 'project.server.config.ProductionConfig')
    if testing:
        app_settings = 'project.server.config.TestingConfig'

    app.config.from_object(app_settings)
    if testing:
        app.config.update({
            "TESTING": True,
        })
    ###
    app.logger.debug("Using ENV({}) = {}".format('APP_SETTINGS', app_settings))
    app.logger.debug("Using database {} (testing={})".format(app.config['SQLALCHEMY_DATABASE_URI'], testing))
    setup_database(app, testing=testing)

    Migrate(app, db)

    login_manager = LoginManager()
    login_manager.init_app(app)

    install_decorator_for_load_user(app, login_manager)
    install_decorator_for_request_loader(app, login_manager)
    ###
    define_appgroup_config(app)
    define_appgroup_data(app)
    define_appgroup_token(app)
    define_appgroup_user(app)
    ###
    @app.cli.command("tests")
    def cli_aaaaa():
        """Runs the unit tests without test coverage."""
        tests = unittest.TestLoader().discover('project/tests', pattern='test*.py')
        result = unittest.TextTestRunner(verbosity=2).run(tests)
        if result.wasSuccessful():
            return 0
        return 1

    #
    bcrypt.init_app(app)
    #
    cache.init_app(app)
    #
    setup_static_routes(app)
    setup_blueprints(app, testing)
    #
    setup_rest_api(app, Api(app))
    #
    return app


def setup_database(app, testing=False):
    if testing:
        m = re.search(r'^sqlite:///(.*)$', app.config['SQLALCHEMY_DATABASE_URI'])
        if m:
            p = Path(m.group(1))
            p.unlink(missing_ok=True)

            with io.open(p, 'wb') as f:
                pass

    db.init_app(app)

    with app.app_context():
        db.create_all()


def setup_static_routes(app):
    app.add_url_rule('/', 'root', root)
    return app


def setup_blueprints(app, testing):
    app.register_blueprint(hits_blueprint, url_prefix='/hits')
    app.register_blueprint(order_blueprint, url_prefix='/order')
    app.register_blueprint(user_blueprint, url_prefix='/user')
    app.register_blueprint(youtube_blueprint, url_prefix='/youtube')
    app.register_blueprint(diary_blueprint, url_prefix='/diary')
    app.register_blueprint(markdown_blueprint, url_prefix='/markdown')
    app.register_blueprint(storage_blueprint, url_prefix='/storage')
    app.register_blueprint(gallery_blueprint, url_prefix='/gallery')

    app.register_blueprint(testing_blueprint, url_prefix='/testing')
    return app


def setup_rest_api(app, api):

    api.add_resource(REST_Order_GET, '/v1/order/<string:order_id>')
    api.add_resource(REST_Order_POST, '/v1/order')
    api.add_resource(REST_Orders_GET, '/v1/orders')
    # app.register_blueprint(v1_order_blueprint)

    api.add_resource(REST_Order_Worker_Reserve, '/v1/order/reserve')
    api.add_resource(REST_Result, '/result/<uuid:result_uuid>')
    # api.add_resource(foo.REST_Order_Workers, '/order/<int:order_id>/workers')
    # api.add_resource(foo.REST_Order_POST, '/order')
    # api.add_resource(foo.REST_Orders, '/orders')

    # api.add_resource(foo.REST_Foos, '/foos')
    # api.add_resource(foo.Todo, '/todos/<todo_id>')
