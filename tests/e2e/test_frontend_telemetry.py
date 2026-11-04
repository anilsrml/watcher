"""Nginx üzerinden gelen istek frontend'in trace, metrik ve logunda görünür. Çalışan VPS lab'ı gerekir."""

import time
import urllib.request

import pytest
from grafana import LAB_IP, eventually, get_json

pytestmark = pytest.mark.skipif(
    not LAB_IP, reason="LAB_BIND_IP gerekli: uv run --env-file .env pytest tests/e2e"
)


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
