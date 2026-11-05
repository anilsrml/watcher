from uuid import uuid4

import pytest

from shop.app import SERVICES, create_app

FRONTEND = "http://frontend:8000"
PRODUCT = "http://product:8000"
CART = "http://cart:8000"
CHECKOUT = "http://checkout:8000"
PAYMENT = "http://payment:8000"


def test_unknown_service_is_rejected():
    with pytest.raises(ValueError):
        create_app("unknown")


@pytest.mark.anyio
async def test_product_list_comes_from_postgres(shop):
    products = (await shop.get(f"{PRODUCT}/products")).json()

    assert len(products) >= 3
    assert {"id", "name", "price_kurus"} <= products[0].keys()


@pytest.mark.anyio
async def test_unknown_product_is_404(shop):
    assert (await shop.get(f"{PRODUCT}/products/999999")).status_code == 404


@pytest.mark.anyio
async def test_cart_keeps_items_per_session(shop):
    session = uuid4().hex
    await shop.post(f"{CART}/carts/{session}/items", json={"product_id": 2})
    await shop.post(f"{CART}/carts/{session}/items", json={"product_id": 2})
    await shop.post(
        f"{CART}/carts/{session}/items", json={"product_id": 3, "quantity": 3}
    )

    assert (await shop.get(f"{CART}/carts/{session}")).json() == {
        "items": {"2": 2, "3": 3}
    }
    assert (await shop.get(f"{CART}/carts/{uuid4().hex}")).json() == {"items": {}}


@pytest.mark.anyio
async def test_cart_can_be_emptied(shop):
    session = uuid4().hex
    await shop.post(f"{CART}/carts/{session}/items", json={"product_id": 1})
    await shop.delete(f"{CART}/carts/{session}")

    assert (await shop.get(f"{CART}/carts/{session}")).json() == {"items": {}}


@pytest.mark.anyio
async def test_payment_approves_only_positive_amounts(shop):
    approved = await shop.post(f"{PAYMENT}/payments", json={"amount_kurus": 1000})

    assert approved.json() == {"status": "approved"}
    assert (
        await shop.post(f"{PAYMENT}/payments", json={"amount_kurus": 0})
    ).status_code == 422


@pytest.mark.anyio
async def test_checkout_charges_cart_total_and_empties_cart(shop):
    session = uuid4().hex
    await shop.post(
        f"{CART}/carts/{session}/items", json={"product_id": 1, "quantity": 2}
    )
    await shop.post(f"{CART}/carts/{session}/items", json={"product_id": 3})

    order = (
        await shop.post(f"{CHECKOUT}/checkout", json={"session_id": session})
    ).json()

    assert order["total_kurus"] == 2 * 89900 + 59900
    assert order["order_id"] > 0
    assert (await shop.get(f"{CART}/carts/{session}")).json() == {"items": {}}


@pytest.mark.anyio
async def test_checkout_rejects_empty_cart(shop):
    response = await shop.post(f"{CHECKOUT}/checkout", json={"session_id": uuid4().hex})

    assert response.status_code == 400


@pytest.mark.anyio
async def test_shopper_can_browse_and_buy(shop):
    home = await shop.get(f"{FRONTEND}/")
    assert home.headers["content-type"].startswith("text/html")
    assert 'href="/product/2"' in home.text

    assert "Akıllı Saat" in (await shop.get(f"{FRONTEND}/product/2")).text

    cart = await shop.post(
        f"{FRONTEND}/cart/add", data={"product_id": "2"}, follow_redirects=True
    )
    assert 'data-product-id="2"' in cart.text

    order = await shop.post(f"{FRONTEND}/checkout")
    assert "Siparişiniz alındı" in order.text
    assert "data-product-id" not in (await shop.get(f"{FRONTEND}/cart")).text


@pytest.mark.anyio
async def test_frontend_passes_shopper_errors_through(shop):
    assert (await shop.get(f"{FRONTEND}/product/999999")).status_code == 404
    unknown = await shop.post(f"{FRONTEND}/cart/add", data={"product_id": "999999"})
    assert unknown.status_code == 404
    assert (await shop.post(f"{FRONTEND}/checkout")).status_code == 400


@pytest.mark.anyio
async def test_shop_counts_page_views_orders_and_payments(shop, counter):
    def snapshot():
        return [
            counter("shop.page_views", page="home"),
            counter("shop.orders"),
            counter("shop.revenue.kurus"),
            counter("shop.payments", status="approved"),
        ]

    before = snapshot()
    await shop.get(f"{FRONTEND}/")
    await shop.post(f"{FRONTEND}/cart/add", data={"product_id": "3"})
    await shop.post(f"{FRONTEND}/checkout")

    assert [a - b for a, b in zip(snapshot(), before)] == [1, 1, 59900, 1]


@pytest.mark.anyio
async def test_every_service_reports_health(shop):
    for name in SERVICES:
        assert (await shop.get(f"http://{name}:8000/healthz")).json() == {
            "status": "ok"
        }
