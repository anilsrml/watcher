"""Ana sayfa → ürün → sepet → ödeme akışı çalışır ve tek trace'te 5 servisi gösterir. Çalışan VPS lab'ı gerekir."""

import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

LAB_IP = os.environ.get("LAB_BIND_IP")

pytestmark = pytest.mark.skipif(
    not LAB_IP, reason="LAB_BIND_IP gerekli: uv run --env-file .env pytest tests/e2e"
)

GRAFANA = f"http://{LAB_IP}:3000/api/datasources/proxy/uid"
SHOP_SERVICES = {"frontend", "product", "cart", "checkout", "payment"}
WAIT_SECONDS = 60


def get_json(path, **params):
    url = f"{GRAFANA}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def eventually(check):
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
def checkout_start():
    browser = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def visit(path, form=None):
        data = None if form is None else urllib.parse.urlencode(form).encode()
        with browser.open(f"http://{LAB_IP}{path}", data=data, timeout=10) as response:
            assert response.status == 200
            return response.read().decode()

    home = visit("/")
    product_id = re.search(r'href="/product/(\d+)"', home).group(1)
    visit(f"/product/{product_id}")
    cart = visit("/cart/add", {"product_id": product_id})
    assert f'data-product-id="{product_id}"' in cart

    start = int(time.time())
    order = visit("/checkout", {})
    assert "Siparişiniz alındı" in order
    return start


def test_checkout_trace_spans_all_shop_services(checkout_start):
    def trace_services():
        found = get_json(
            "tempo/api/search",
            q='{ resource.service.name = "frontend" && name = "POST /checkout" }',
            start=checkout_start - 5,
            end=int(time.time()) + 5,
        ).get("traces")
        if not found:
            return None
        trace = get_json(f"tempo/api/traces/{found[0]['traceID']}")
        services = {
            attr["value"]["stringValue"]
            for batch in trace.get("batches") or trace.get("resourceSpans") or []
            for attr in batch["resource"]["attributes"]
            if attr["key"] == "service.name"
        }
        return services if SHOP_SERVICES <= services else None

    assert eventually(trace_services) == SHOP_SERVICES
