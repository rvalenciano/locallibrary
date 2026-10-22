# Running in a container

The image is built from the `Dockerfile` at the repo root (multi-stage, Python slim base, dependencies installed with `uv`). It runs `uvicorn locallibrary.asgi:application` on port 8000 as UID 10001 (non-root). Static files are collected at build time and served by WhiteNoise, so no separate static server is needed.

## Build and run

```sh
docker build -t locallibrary .

docker run --rm -p 8000:8000 \
  -e SECRET_KEY=change-me \
  -e DJANGO_ALLOWED_HOSTS=localhost \
  locallibrary

curl -i http://localhost:8000/healthz/
```

Without `DATABASE_URL` the app falls back to SQLite inside the container (not persisted). Set `DATABASE_URL` for real use. The image only starts the server; it never runs migrations or indexing on startup (see [One-off commands](#one-off-commands)).

## Environment variables

The app does not load `.env` files. The runtime must inject the variables. `.env.example` is a template for `docker run --env-file` (or compose); copy it and replace the placeholders.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes, unless `DJANGO_DEBUG` is on | none (startup fails) | Django secret key. |
| `DATABASE_URL` | No | SQLite `db.sqlite3` | Database URL, e.g. `postgres://user:pass@host:5432/db`. |
| `DJANGO_DEBUG` | No | off | `1`/`true`/`yes`/`on` enables debug. Leave off in production. |
| `DJANGO_ALLOWED_HOSTS` | Yes in production | empty | Comma-separated hostnames Django will serve. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | When behind TLS | empty | Comma-separated origins including scheme, e.g. `https://library.example.com`. |
| `DJANGO_TRUST_PROXY_PROTO` | Behind a TLS-terminating proxy | off | `1`/`true`/`yes`/`on` makes Django trust `X-Forwarded-Proto`. |
| `FORWARDED_ALLOW_IPS` | Behind a proxy | `127.0.0.1` | Proxy address(es)/CIDR whose forwarded headers uvicorn trusts. |
| `OPENSEARCH_URL` | No | `http://localhost:9200` | OpenSearch endpoint. If it is unreachable, search falls back to the database. |
| `WEB_CONCURRENCY` | No | `1` | Number of uvicorn worker processes (read by uvicorn). |

### Behind an ingress

The image starts uvicorn with `--proxy-headers`, but uvicorn only trusts forwarded headers from `127.0.0.1` by default. Behind an ingress or load balancer, set `FORWARDED_ALLOW_IPS` to the proxy's address or CIDR, and set `DJANGO_TRUST_PROXY_PROTO=1`. Without both, Django will not see the request as HTTPS (redirects, secure cookies and CSRF origin checks misbehave).

## Probe endpoints

Both are answered by middleware before host validation, so probes addressed to the pod IP work without being listed in `DJANGO_ALLOWED_HOSTS`.

- `/healthz/` (liveness): returns `200 ok`. Has no dependencies, so it never fails because of the database or OpenSearch.
- `/functionalz/` (readiness): returns JSON such as `{"database": "up", "opensearch": "down"}`. Status is `503` only when the database is down. OpenSearch being down is reported in the body only and still returns `200`, because search degrades to a database fallback.

## One-off commands

Run these as Jobs (or `docker run` with a command override), never at container startup, so that multiple replicas do not race. Pass the same environment as the app (`DATABASE_URL`, `OPENSEARCH_URL`, `SECRET_KEY`, ...).

```sh
docker run --rm --env-file .env locallibrary python manage.py migrate
docker run --rm --env-file .env locallibrary python manage.py search_index
```

- `migrate` applies database migrations. Because old and new pods run side by side during a rolling deploy, migrations must be backward-compatible with the previous release (e.g. add columns before using them, drop them in a later release).
- `search_index` rebuilds the OpenSearch indexes (`catalog-book`, `catalog-author`) from the database. Run it after the first deploy and whenever the index needs rebuilding.

## Deploying

For the human deployment checklist, see issue [#22](https://github.com/rvalenciano/locallibrary/issues/22).
