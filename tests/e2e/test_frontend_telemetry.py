"""Nginx üzerinden gelen istek frontend'in trace, metrik ve logunda görünür. Çalışan VPS lab'ı gerekir."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

LAB_IP = os.environ.get("LAB_BIND_IP")

pytestmark = pytest.mark.skipif(
    not LAB_IP, reason="LAB_BIND_IP gerekli: uv run --env-file .env pytest tests/e2e"
)

# Backend portları kapalı; sorgular Grafana'nın datasource proxy'sinden geçer.
GRAFANA = f"http://{LAB_IP}:3000/api/datasources/proxy/uid"
WAIT_SECONDS = 60


def get_json(path, **params):
    url = f"{GRAFANA}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def eventually(check):
    # Tempo, ilk trace yeni gelirken bir kez 400 döndü; süre bitene kadar hatayı "henüz yok" say.
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            result, error = check(), None
        except urllib.error.HTTPError as exc:
            result, error = None, exc
        if result or time.monotonic() >= deadline:
            if error:
                raise error
            return result
        time.sleep(3)


@pytest.fixture(scope="module")
def request_start():
    start = int(time.time())
    with urllib.request.urlopen(f"http://{LAB_IP}/", timeout=5) as response:
        assert response.status == 200
    return start


def test_trace_reaches_tempo(request_start):
    def traces():
        return get_json(
            "tempo/api/search",
            q='{ resource.service.name = "frontend" }',
            start=request_start - 5,
            end=int(time.time()) + 5,
        ).get("traces")

    assert eventually(traces)


def test_request_metric_reaches_prometheus(request_start):
    def series():
        return get_json(
            "prometheus/api/v1/query",
            query='{__name__=~"http_server_.*_count", job="frontend"}',
        )["data"]["result"]

    assert eventually(series)


def test_log_reaches_loki(request_start):
    def logs():
        return get_json(
            "loki/loki/api/v1/query_range",
            query='{service_name="frontend"} |= "home page served"',
            start=(request_start - 5) * 10**9,
        )["data"]["result"]

    assert eventually(logs)
