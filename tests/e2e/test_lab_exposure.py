"""Lab'a yalnız Tailscale üzerinden erişildiğini doğrular. Çalışan VPS lab'ı gerekir."""

import os
import socket
import urllib.request

import pytest

LAB_IP = os.environ.get("LAB_BIND_IP")
PUBLIC_IP = os.environ.get("WATCHER_PUBLIC_IP")

pytestmark = pytest.mark.skipif(
    not (LAB_IP and PUBLIC_IP),
    reason="LAB_BIND_IP ve WATCHER_PUBLIC_IP gerekli: uv run --env-file .env pytest tests/e2e",
)

BACKEND_PORTS = [3100, 3200, 4040, 4317, 4318, 9090]


def http_status(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status


def test_grafana_reachable_over_tailscale():
    assert http_status(f"http://{LAB_IP}:3000/api/health") == 200


def test_nginx_reachable_over_tailscale():
    assert http_status(f"http://{LAB_IP}/") == 200


@pytest.mark.parametrize("port", [80, 3000, *BACKEND_PORTS])
def test_port_closed_on_public_ip(port):
    with pytest.raises(OSError):
        socket.create_connection((PUBLIC_IP, port), timeout=3).close()


@pytest.mark.parametrize("port", BACKEND_PORTS)
def test_backend_port_closed_over_tailscale(port):
    with pytest.raises(OSError):
        socket.create_connection((LAB_IP, port), timeout=3).close()
