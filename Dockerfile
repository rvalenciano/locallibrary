ARG PYTHON_VERSION=3.14.9

FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY manage.py ./
COPY locallibrary ./locallibrary
COPY catalog ./catalog

# Throwaway key: only needed so settings import; never persisted as runtime config.
RUN SECRET_KEY=build-only-throwaway /opt/venv/bin/python manage.py collectstatic --noinput


FROM python:${PYTHON_VERSION}-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /app /app

WORKDIR /app
USER 10001
EXPOSE 8000

# Starts the server only; run `migrate` / `search_index` as one-off command overrides.
# WEB_CONCURRENCY is read natively by uvicorn (default 1).
# Operators must set FORWARDED_ALLOW_IPS to the ingress/proxy address or CIDR;
# otherwise uvicorn trusts forwarded headers only from 127.0.0.1.
CMD ["uvicorn", "locallibrary.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
