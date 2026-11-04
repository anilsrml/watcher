import pytest
from fastapi.testclient import TestClient

from shop.app import create_app


def test_frontend_home_page_is_html():
    response = TestClient(create_app("frontend")).get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Watcher Shop" in response.text


def test_unknown_service_is_rejected():
    with pytest.raises(ValueError):
        create_app("unknown")
