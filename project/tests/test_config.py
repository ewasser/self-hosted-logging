# project/tests/test_config.py
import json
import datetime

import pytest

from pathlib import Path

import project.server.startup
from project.server.database import db
from project.server.models import User, Hit

# class TestDevelopmentConfig(flask_unittest.AppTestCase):
#
#     @pytest.fixture
#     def client():
#         db_fd, flaskr.app.config['DATABASE'] = tempfile.mkstemp()
#         flaskr.app.config['TESTING'] = True
#
#         with flaskr.app.test_client() as client:
#             with flaskr.app.app_context():
#                 flaskr.init_db()
#             yield client
#
#         os.close(db_fd)
#         os.unlink(flaskr.app.config['DATABASE'])
#


@pytest.fixture
def app():
    app = project.server.startup.create_app(testing=True)
    return app


def test_config(app):
    assert Path(app.config['SQLALCHEMY_DATABASE_URI']).name == 'desktop_testing.db'


def test_emptiness(app):
    with app.test_client() as client:
        response = client.get('/user/status')
        assert response.status_code == 200

        data = json.loads(response.data.decode())
        assert data == {
            'user': {'active': False,
                     'anonymous': True,
                     'authenticated': False,
                     'id': None},
        }


def test_user(app):

    with app.app_context():
        user = User(
            email='test1@test.com',
            password='test1'
        )
        db.session.add(user)
        db.session.commit()

        auth_token = user.encode_auth_token(user.id)
        assert isinstance(auth_token, str)

    headers = {'Authorization': 'Bearer {auth_token}'.format(auth_token=auth_token)}

    with app.test_client() as client:
        response = client.get('/user/status', headers=headers)

        assert response.status_code == 200

        data = json.loads(response.data.decode())
        assert data == {
            'user': {'active': True,
                     'anonymous': False,
                     'authenticated': True,
                     'id': '1'},
        }


def test_user_with_outdated_jwt(app):

    with app.app_context():
        user = User(email='test2@test.com', password='test2')
        db.session.add(user)
        db.session.commit()

        auth_token = user.encode_auth_token(user.id,
                                            period=datetime.timedelta(seconds=-1))
        assert isinstance(auth_token, str)

    headers = {'Authorization': 'Bearer {auth_token}'.format(auth_token=auth_token)}

    with app.test_client() as client:
        response = client.get('/user/status', headers=headers)

        assert response.status_code == 200

        data = json.loads(response.data.decode())
        assert data == {
            'user': {'active': False,
                     'anonymous': True,
                     'authenticated': False,
                     'id': None},
        }


def test_insert_defect_json(app):

    with app.app_context():
        user = User(email='test2@test.com', password='test2')
        db.session.add(user)
        db.session.commit()

        auth_token = user.encode_auth_token(user.id,
                                            period=datetime.timedelta(minutes=1))
        assert isinstance(auth_token, str)

    headers = {'Authorization': 'Bearer {auth_token}'.format(auth_token=auth_token)}

    with app.test_client() as client:
        response = client.post('/hits/collection', headers=headers, json={})
        assert response.status_code == 200

        assert json.loads(response.data.decode()) == {'message': "Missing hash key 'hits'", 'status': 'ERROR'}


def test_insert(app):

    with app.app_context():
        user = User(email='test3@test.com', password='test3')
        db.session.add(user)
        db.session.commit()

        auth_token = user.encode_auth_token(user.id,
                                            period=datetime.timedelta(days=1))
        assert isinstance(auth_token, str)

    headers = {'Authorization': 'Bearer {auth_token}'.format(auth_token=auth_token)}

    with app.test_client() as client:
        json_data = {
            'hits': [
                {
                    'url': 'https://www.google.de',
                    'timestamp_ms': datetime.datetime.now().timestamp()*1000,
                    'title': "Google it",
                },
                {
                    'url': 'https://www.google.de',
                    'timestamp_ms': datetime.datetime.now().timestamp() * 1000,
                    'title': "Google it",
                }
            ]
        }

        response = client.post('/hits/collection', headers=headers, json=json_data)
        assert response.status_code == 200

        assert json.loads(response.data.decode()) == {'status': 'OK'}

    with app.app_context():
        hit = Hit.query.first()
        assert Hit.query.count() == 1
        db.session.commit()

        assert hit.url == 'https://www.google.de'
        assert isinstance(hit.mtime, datetime.datetime)
        assert hit.title == 'Google it'
