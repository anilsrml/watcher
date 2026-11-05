"""Koşucu kısa bir deneme koşusunu baştan sona yürütür. Çalışan VPS lab'ı ve dizüstünde Docker gerekir (~2,5 dk)."""

import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest
from grafana import LAB_IP, eventually, get_json

import runner

pytestmark = pytest.mark.skipif(
    not (LAB_IP and os.environ.get("GRAFANA_ADMIN_PASSWORD")),
    reason="LAB_BIND_IP ve GRAFANA_ADMIN_PASSWORD gerekli: uv run --env-file .env pytest tests/e2e",
)

ROOT = Path(__file__).parents[2]


def nanoseconds(iso):
    return int(datetime.fromisoformat(iso).timestamp() * 10**9)


def v1_1_0_deployed_since(start_ms):
    # Grafana `from`'u `to` olmadan yok sayar; eski v1.1.0 marker'ları eşleşmesin.
    window = {"from": start_ms, "to": start_ms + 600_000}
    tags = {"tags": ["deploy", "service:checkout", "version:v1.1.0"]}
    query = urllib.parse.urlencode(tags | window, doseq=True)
    url = f"http://{LAB_IP}:3000/api/annotations?{query}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return bool(json.load(response))


def checkout_two_products():
    """Bozuk sürümün hata verdiği çok ürünlü sepetle öder; HTTP durumunu döner."""
    browser = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    for product_id in ("1", "3"):
        data = urllib.parse.urlencode({"product_id": product_id}).encode()
        browser.open(f"http://{LAB_IP}/cart/add", data=data, timeout=10).close()
    try:
        browser.open(f"http://{LAB_IP}/checkout", data=b"", timeout=10).close()
    except urllib.error.HTTPError as error:
        return error.code
    return 200


def test_trial_deploy_run_breaks_checkout_then_rolls_back(tmp_path):
    start_ms = int(time.time() * 1000)
    run = subprocess.Popen(
        [sys.executable, "scenarios/runner.py", "ops-checkout-deploy-01"]
        + ["--trial", "20,60,10", "--runs-dir", str(tmp_path)],
        cwd=ROOT,
    )
    try:
        deadline = time.monotonic() + 75
        while not v1_1_0_deployed_since(start_ms):
            assert run.poll() is None and time.monotonic() < deadline, "v1.1.0 gelmedi"
            time.sleep(2)
        # Rastgele trafiğe güvenme: çok ürünlü sepeti test kendisi öder.
        assert checkout_two_products() == 500
    finally:
        run.wait(timeout=300)  # koşucu checkout'u v1.0.0'a döndürmeden test bitmesin
    assert run.returncode == 0

    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert record["trial"] and not record["aborted"] and record["k6_exit"] == 0
    assert record["deploy"]["version"] == "v1.1.0"
    env = runner.vps(
        "inspect",
        "watcher-lab-checkout-1",
        "--format",
        "{{json .Config.Env}}",
        capture_output=True,
        text=True,
    )
    assert runner.release(json.loads(env.stdout)) == "v1.0.0"

    def checkout_errors():
        streams = get_json(
            "loki/loki/api/v1/query_range",
            query='{service_name="checkout"} |= "unhandled error"',
            start=nanoseconds(record["deploy"]["at"]),
            end=nanoseconds(record["deploy"]["rollback_at"]),
        )["data"]["result"]
        return [line for s in streams for _, line in s["values"]]

    assert eventually(checkout_errors)
