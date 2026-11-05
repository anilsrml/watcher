"""Watcher Shop: tek kod tabanı, rolü SERVICE ile seçilen 5 servis."""

import logging
import os
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from html import escape

import asyncpg
import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from opentelemetry import metrics
from pydantic import BaseModel, Field

logger = logging.getLogger("shop")
logger.setLevel(logging.INFO)

# İş metrikleri. Dönüşüm ve sipariş/dk uygulamada değil, PromQL ile hesaplanır.
meter = metrics.get_meter("shop")
PAGE_VIEWS = meter.create_counter(
    "shop.page_views", description="Sayfa görüntülemeleri"
)
ORDERS = meter.create_counter("shop.orders", description="Tamamlanan siparişler")
REVENUE = meter.create_counter(
    "shop.revenue.kurus", description="Sipariş cirosu, kuruş"
)
PAYMENTS = meter.create_counter("shop.payments", description="Ödeme sonuçları")


PRODUCTS = [
    (1, "Kablosuz Kulaklık", 89900),
    (2, "Akıllı Saat", 149900),
    (3, "Bluetooth Hoparlör", 59900),
    (4, "Mekanik Klavye", 119900),
    (5, "Oyuncu Mouse", 44900),
    (6, "USB-C Şarj Aleti", 24900),
]


def url(service: str) -> str:
    return f"http://{service}:8000"


async def _product_schema(db: asyncpg.Pool) -> None:
    await db.execute(
        "CREATE TABLE IF NOT EXISTS products (id int PRIMARY KEY, name text NOT NULL, price_kurus int NOT NULL)"
    )
    await db.executemany(
        "INSERT INTO products (id, name, price_kurus) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
        PRODUCTS,
    )


def page(body: str) -> str:
    return (
        '<!doctype html>\n<html lang="tr">\n<head><meta charset="utf-8"><title>Watcher Shop</title></head>\n'
        f'<body><h1><a href="/">Watcher Shop</a></h1>\n{body}\n<p><a href="/cart">Sepet</a></p></body>\n</html>\n'
    )


def price(kurus: int) -> str:
    return f"{kurus // 100},{kurus % 100:02d} TL"


def _frontend(app: FastAPI) -> None:
    @app.middleware("http")
    async def session_cookie(request: Request, call_next):
        request.state.session = request.cookies.get("sid") or uuid.uuid4().hex
        response = await call_next(request)
        if "sid" not in request.cookies:
            response.set_cookie(
                "sid", request.state.session, httponly=True, samesite="lax"
            )
        return response

    async def backend(method: str, service: str, path: str, **kwargs) -> httpx.Response:
        response = await app.state.http.request(
            method, f"{url(service)}{path}", **kwargs
        )
        if response.status_code in (400, 404):
            raise HTTPException(response.status_code, response.json().get("detail"))
        return response.raise_for_status()

    @app.get("/", response_class=HTMLResponse)
    async def home() -> str:
        products = (await backend("GET", "product", "/products")).json()
        rows = "".join(
            f'<li><a href="/product/{p["id"]}">{escape(p["name"])}</a> {price(p["price_kurus"])}</li>'
            for p in products
        )
        logger.info("home page served")
        PAGE_VIEWS.add(1, {"page": "home"})
        return page(f"<ul>{rows}</ul>")

    @app.get("/product/{product_id}", response_class=HTMLResponse)
    async def product_page(product_id: int) -> str:
        p = (await backend("GET", "product", f"/products/{product_id}")).json()
        PAGE_VIEWS.add(1, {"page": "product"})
        return page(
            f"<h2>{escape(p['name'])}</h2><p>{price(p['price_kurus'])}</p>"
            '<form method="post" action="/cart/add">'
            f'<input type="hidden" name="product_id" value="{p["id"]}"><button>Sepete ekle</button></form>'
        )

    @app.post("/cart/add")
    async def add_to_cart(
        request: Request, product_id: int = Form()
    ) -> RedirectResponse:
        await backend("GET", "product", f"/products/{product_id}")
        item = {"product_id": product_id}
        await backend(
            "POST", "cart", f"/carts/{request.state.session}/items", json=item
        )
        return RedirectResponse("/cart", status_code=303)

    @app.get("/cart", response_class=HTMLResponse)
    async def cart_page(request: Request) -> str:
        items = (
            await backend("GET", "cart", f"/carts/{request.state.session}")
        ).json()["items"]
        products = {
            str(p["id"]): p
            for p in (await backend("GET", "product", "/products")).json()
        }
        rows = "".join(
            f'<li data-product-id="{pid}">{escape(products[pid]["name"])} × {qty}</li>'
            for pid, qty in items.items()
        )
        total = sum(products[pid]["price_kurus"] * qty for pid, qty in items.items())
        checkout = (
            '<form method="post" action="/checkout"><button>Ödeme yap</button></form>'
        )
        PAGE_VIEWS.add(1, {"page": "cart"})
        body = f"<h2>Sepet</h2><ul>{rows}</ul><p>Toplam: {price(total)}</p>{checkout if items else ''}"
        return page(body)

    @app.post("/checkout", response_class=HTMLResponse)
    async def checkout(request: Request) -> str:
        order_request = {"session_id": request.state.session}
        order = (
            await backend("POST", "checkout", "/checkout", json=order_request)
        ).json()
        PAGE_VIEWS.add(1, {"page": "checkout"})
        return page(
            f"<h2>Siparişiniz alındı</h2><p>Sipariş #{order['order_id']}, {price(order['total_kurus'])}</p>"
        )


def _product(app: FastAPI) -> None:
    app.state.schema = _product_schema

    @app.get("/products")
    async def list_products() -> list[dict]:
        rows = await app.state.db.fetch(
            "SELECT id, name, price_kurus FROM products ORDER BY id"
        )
        return [dict(row) for row in rows]

    @app.get("/products/{product_id}")
    async def get_product(product_id: int) -> dict:
        row = await app.state.db.fetchrow(
            "SELECT id, name, price_kurus FROM products WHERE id = $1", product_id
        )
        if row is None:
            raise HTTPException(404, "product not found")
        return dict(row)


class CartItem(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)


def _cart(app: FastAPI) -> None:
    app.state.uses_redis = True

    def key(session: str) -> str:
        return f"cart:{session}"

    @app.post("/carts/{session}/items", status_code=204)
    async def add_item(session: str, item: CartItem) -> None:
        await app.state.redis.hincrby(key(session), str(item.product_id), item.quantity)
        await app.state.redis.expire(key(session), 86400)

    @app.get("/carts/{session}")
    async def get_cart(session: str) -> dict:
        items = await app.state.redis.hgetall(key(session))
        return {"items": {pid.decode(): int(qty) for pid, qty in items.items()}}

    @app.delete("/carts/{session}", status_code=204)
    async def empty_cart(session: str) -> None:
        await app.state.redis.delete(key(session))


class Payment(BaseModel):
    amount_kurus: int = Field(gt=0)


def _payment(app: FastAPI) -> None:
    @app.post("/payments")
    async def pay(payment: Payment) -> dict:
        logger.info("payment approved")
        PAYMENTS.add(1, {"status": "approved"})
        return {"status": "approved"}


async def _checkout_schema(db: asyncpg.Pool) -> None:
    await db.execute(
        "CREATE TABLE IF NOT EXISTS orders (id serial PRIMARY KEY, session_id text NOT NULL,"
        " total_kurus int NOT NULL, created_at timestamptz NOT NULL DEFAULT now())"
    )


class CheckoutRequest(BaseModel):
    session_id: str


def _bundle_discount(items: dict[str, int], prices: dict[str, int]) -> int:
    """Birden fazla farklı ürünlü sepette en ucuz üründen %10 indirim."""
    if len(items) < 2:
        return 0
    cheapest = min(items, key=prices.get)
    return prices[int(cheapest)] // 10


def _checkout(app: FastAPI) -> None:
    app.state.schema = _checkout_schema
    # shortcut: tek image olduğu için v1.1.0'ın kodu sürüm değişkeniyle açılır; ops-checkout-deploy-01 bu sürümün hatasına dayanır.
    bundle_discount = os.environ.get("SERVICE_VERSION", "v1.0.0") == "v1.1.0"

    @app.post("/checkout")
    async def checkout(request: CheckoutRequest) -> dict:
        http = app.state.http
        cart_url = f"{url('cart')}/carts/{request.session_id}"
        items = (await http.get(cart_url)).raise_for_status().json()["items"]
        if not items:
            raise HTTPException(400, "cart is empty")
        products = (
            (await http.get(f"{url('product')}/products")).raise_for_status().json()
        )
        prices = {str(p["id"]): p["price_kurus"] for p in products}
        total = sum(prices[pid] * qty for pid, qty in items.items())
        if bundle_discount:
            total -= _bundle_discount(items, prices)
        payment = {"amount_kurus": total}
        (await http.post(f"{url('payment')}/payments", json=payment)).raise_for_status()
        order_id = await app.state.db.fetchval(
            "INSERT INTO orders (session_id, total_kurus) VALUES ($1, $2) RETURNING id",
            request.session_id,
            total,
        )
        (await http.delete(cart_url)).raise_for_status()
        logger.info("order placed")
        ORDERS.add(1)
        REVENUE.add(total)
        return {"order_id": order_id, "total_kurus": total}


SERVICES = {
    "frontend": _frontend,
    "product": _product,
    "cart": _cart,
    "checkout": _checkout,
    "payment": _payment,
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        if app.state.http is None:
            app.state.http = await stack.enter_async_context(
                httpx.AsyncClient(timeout=5)
            )
        if app.state.schema is not None:
            app.state.db = await asyncpg.create_pool(
                os.environ["DATABASE_URL"], min_size=1, max_size=10
            )
            stack.push_async_callback(app.state.db.close)
            await app.state.schema(app.state.db)
        if app.state.uses_redis:
            app.state.redis = redis.from_url(os.environ["REDIS_URL"])
            stack.push_async_callback(app.state.redis.aclose)
        yield


def create_app(service: str) -> FastAPI:
    if service not in SERVICES:
        raise ValueError(f"unknown service: {service}")
    app = FastAPI(title=f"watcher-shop-{service}", lifespan=_lifespan)
    app.state.http = None
    app.state.schema = None
    app.state.uses_redis = False
    SERVICES[service](app)

    @app.exception_handler(Exception)
    async def log_unhandled(request: Request, exc: Exception) -> PlainTextResponse:
        # Yakalanmamış hata, stack trace'iyle uygulama logundan Loki'ye gitsin.
        logger.error(
            "unhandled error on %s %s", request.method, request.url.path, exc_info=exc
        )
        return PlainTextResponse("Internal Server Error", status_code=500)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    return app
