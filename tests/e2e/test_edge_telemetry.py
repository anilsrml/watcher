"""Nginx logu, istemci IP'si, rate limit ve host/container metrikleri sorgulanabilir. Çalışan VPS lab'ı gerekir."""

import json
import random
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from grafana import LAB_IP, eventually, get_json

pytestmark = pytest.mark.skipif(
    not LAB_IP, reason="LAB_BIND_IP gerekli: uv run --env-file .env pytest tests/e2e"
)


def status_from(client_ip, user_agent="watcher-e2e"):
    request = urllib.request.Request(
        f"http://{LAB_IP}/",
        headers={"X-Forwarded-For": client_ip, "User-Agent": user_agent},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def random_ip(prefix):
    return f"{prefix}.{random.randint(1, 254)}"


def test_access_log_reaches_loki_with_forwarded_client_ip():
    client_ip, marker = random_ip("203.0.113"), uuid.uuid4().hex
    start = int(time.time())
    assert status_from(client_ip, f"watcher-e2e/{marker}") == 200

    def lines():
        streams = get_json(
            "loki/loki/api/v1/query_range",
            query=f'{{service_name="nginx"}} |= "{marker}"',
            start=(start - 5) * 10**9,
        )["data"]["result"]
        return [json.loads(line) for s in streams for _, line in s["values"]]

    entry = eventually(lines)[0]
    assert entry["remote_addr"] == client_ip
    assert entry["status"] == 200
    assert entry["path"] == "/"


def test_rate_limit_rejects_burst_from_one_ip():
    client_ip = random_ip("198.51.100")
    with ThreadPoolExecutor(max_workers=20) as pool:
        statuses = list(pool.map(lambda _: status_from(client_ip), range(80)))

    assert 429 in statuses


def test_rate_limit_spares_many_ips():
    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(lambda i: status_from(f"192.0.2.{i}"), range(1, 41)))

    assert set(statuses) == {200}


@pytest.mark.parametrize("metric", ["system_memory_usage", "container_memory_usage"])
def test_infra_metric_reaches_prometheus(metric):
    def series():
        return get_json("prometheus/api/v1/query", query=f'{{__name__=~"{metric}.*"}}')[
            "data"
        ]["result"]

    assert eventually(series)
