"""deploy.py servisi yeni sürümle başlatır; Grafana'da marker, telemetride sürüm görünür. Çalışan VPS lab'ı gerekir."""

import http.cookiejar
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from grafana import LAB_IP, eventually, get_json

pytestmark = pytest.mark.skipif(
    not (LAB_IP and os.environ.get("GRAFANA_ADMIN_PASSWORD")),
    reason="LAB_BIND_IP ve GRAFANA_ADMIN_PASSWORD gerekli: uv run --env-file .env pytest tests/e2e",
)

ROOT = Path(__file__).parents[2]


def deploy(service, version):
    subprocess.run(
        [sys.executable, "lab/deploy.py", service, version], cwd=ROOT, check=True
    )


def annotations(**params):
    query = urllib.parse.urlencode(params, doseq=True)
    with urllib.request.urlopen(
        f"http://{LAB_IP}:3000/api/annotations?{query}", timeout=10
    ) as r:
        return json.load(r)


def buy_one_product():
    """payment'ın yeni sürümü çağrılsın diye bir satın alma yapar."""
    browser = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    for path, form in [("/cart/add", {"product_id": "1"}), ("/checkout", {})]:
        data = urllib.parse.urlencode(form).encode()
        browser.open(f"http://{LAB_IP}{path}", data=data, timeout=10).close()


@pytest.fixture
def payment_version():
    version = f"v1.0.{random.randint(100, 999)}"
    yield version
    deploy("payment", "v1.0.0")


def test_deploy_leaves_marker_and_version_in_telemetry(payment_version):
    start_ms = int(time.time() * 1000)
    deploy("payment", payment_version)

    marks = annotations(
        tags=["deploy", "service:payment", f"version:{payment_version}"]
    )
    assert len(marks) == 1 and marks[0]["time"] >= start_ms

    buy_one_product()

    def version_series():
        # otel-lgtm service.version'ı her metriğe service_version etiketi olarak ekler.
        query = f'{{job="payment", service_version="{payment_version}"}}'
        return get_json("prometheus/api/v1/query", query=query)["data"]["result"]

    assert eventually(version_series)


def test_anonymous_grafana_is_read_only():
    body = json.dumps(
        {"time": int(time.time() * 1000), "text": "anonim yazma denemesi"}
    ).encode()
    request = urllib.request.Request(
        f"http://{LAB_IP}:3000/api/annotations",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=10)
    assert error.value.code in (401, 403)
