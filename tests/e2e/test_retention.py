"""Telemetri en az 90 gün saklanır: koşu pencereleri sonradan yeniden sorgulanır. Çalışan VPS lab'ı gerekir."""

import urllib.request

import pytest
from grafana import GRAFANA, LAB_IP, get_json

pytestmark = pytest.mark.skipif(
    not LAB_IP, reason="LAB_BIND_IP gerekli: uv run --env-file .env pytest tests/e2e"
)


def config(datasource):
    with urllib.request.urlopen(f"{GRAFANA}/{datasource}", timeout=10) as response:
        return response.read().decode()


def test_prometheus_keeps_90_days():
    info = get_json("prometheus/api/v1/status/runtimeinfo")["data"]

    assert info["storageRetention"] == "90d"


def test_tempo_keeps_90_days():
    tempo = config("tempo/status/config")

    assert tempo.count("block_retention: 2160h0m0s") == 2
    assert "block_retention: 336h" not in tempo


def test_loki_never_deletes_logs():
    # Retention kapalıyken Loki logları silmez.
    assert "retention_enabled: false" in config("loki/config")
