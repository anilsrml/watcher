# Build context: repo kökü (pyproject.toml ve uv.lock için).
FROM python:3.12.15-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY lab/app/shop ./shop

ENV PATH="/app/.venv/bin:$PATH"
CMD ["opentelemetry-instrument", "uvicorn", "shop.main:app", "--host", "0.0.0.0", "--port", "8000"]
