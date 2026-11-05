import os
from contextlib import AsyncExitStack

import httpx
import pytest
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from shop.app import SERVICES, create_app

# Gerçek OTel SDK; testler sayaçları bellekteki okuyucudan okur.
METRICS = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(metric_readers=[METRICS]))

# Yerel test altyapısı: docker --context default compose -f lab/compose.test.yaml up -d
os.environ.setdefault(
    "DATABASE_URL", "postgresql://watcher:test@127.0.0.1:55432/watcher"
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:56379/0")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def counter():
    """Bir sayacın, verilen etiketlere uyan veri noktalarının toplamı (kümülatif)."""

    def value(name, **attributes):
        data = METRICS.get_metrics_data()
        return sum(
            point.value
            for resource in (data.resource_metrics if data else [])
            for scope in resource.scope_metrics
            for metric in scope.metrics
            if metric.name == name
            for point in metric.data.data_points
            if attributes.items() <= dict(point.attributes).items()
        )

    return value


@pytest.fixture
async def shop():
    """5 servis süreç içinde; birbirlerine ağ yerine ASGI üzerinden, gerçek Postgres ve Redis ile bağlanır."""
    apps = {name: create_app(name) for name in SERVICES}
    mounts = {
        f"http://{name}:8000": httpx.ASGITransport(app) for name, app in apps.items()
    }
    async with AsyncExitStack() as stack:
        internal = await stack.enter_async_context(httpx.AsyncClient(mounts=mounts))
        for app in apps.values():
            app.state.http = internal
            await stack.enter_async_context(app.router.lifespan_context(app))
        yield await stack.enter_async_context(httpx.AsyncClient(mounts=mounts))
