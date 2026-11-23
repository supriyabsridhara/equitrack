import mongomock
import pytest
from flask import Flask

from app.integration import init_alerts_and_ui
from dev.mock_server import create_mock_app


@pytest.fixture
def db():
    return mongomock.MongoClient()["equitrack_test"]


@pytest.fixture
def app(db):
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.extensions["mongo_db"] = db
    init_alerts_and_ui(flask_app)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def svc(app):
    return app.extensions["alert_service"]


@pytest.fixture
def mock_client():
    """Full mock backend (Member 1 stand-in + Member 2 alerts) for end-to-end flows."""
    return create_mock_app().test_client()
