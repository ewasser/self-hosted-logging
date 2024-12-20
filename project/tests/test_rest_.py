# project/tests/test_link.py

import pytest

# project/tests/test_config.py
import json
import datetime

import pytest

import project.server.startup

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
