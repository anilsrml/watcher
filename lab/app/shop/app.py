"""Watcher Shop: tek kod tabanı, rolü SERVICE ile seçilen 5 servis."""

import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger("shop")
logger.setLevel(logging.INFO)

HOME_PAGE = """<!doctype html>
<html lang="tr">
<head><meta charset="utf-8"><title>Watcher Shop</title></head>
<body><h1>Watcher Shop</h1></body>
</html>
"""


def _frontend(app: FastAPI) -> None:
    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        logger.info("home page served")
        return HOME_PAGE


SERVICES = {"frontend": _frontend}


def create_app(service: str) -> FastAPI:
    if service not in SERVICES:
        raise ValueError(f"unknown service: {service}")
    app = FastAPI(title=f"watcher-shop-{service}")
    SERVICES[service](app)
    return app
