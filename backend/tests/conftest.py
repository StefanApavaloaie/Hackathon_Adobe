# Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

FRONTEND = "http://localhost:5173"


@pytest.fixture
def make_settings():
    def factory(**overrides) -> Settings:
        overrides.setdefault("frontend_origin", FRONTEND)
        return Settings(_env_file=None, **overrides)

    return factory


@pytest.fixture
def client(make_settings) -> TestClient:
    """An app with development login allowed, as in a local .env."""
    settings = make_settings(allow_dev_auth=True)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)
