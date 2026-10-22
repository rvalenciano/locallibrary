# Running in a container

The intended target is Kubernetes (pods, Jobs for one-off commands, liveness/readiness probes); `docker run` works for local checks. The image is built from the `Dockerfile` at the repo root (multi-stage, Python slim base, dependencies installed with `uv`). It runs `uvicorn locallibrary.asgi:application` on port 8000 as UID 10001 (non-root). Static files are collected at build time and served by WhiteNoise, so no separate static server is needed.

## Build and run

```sh
docker build -t locallibrary .

docker run --rm -p 8000:8000 \
  -e SECRET_KEY=change-me \
  -e DJANGO_ALLOWED_HOSTS=localhost \
  locallibrary

curl -i http://localhost:8000/healthz/
```

Without `DATABASE_URL` the app falls back to SQLite inside the container (not persisted). That database starts empty because nothing migrates at startup, so only `/healthz/` and `/functionalz/` work until you run `python manage.py migrate` in that same container (e.g. `docker exec <container> python manage.py migrate`), or point `DATABASE_URL` at an already-migrated Postgres. The image never runs migrations or indexing on startup (see [One-off commands](#one-off-commands)).

## Environment variables

The app does not load `.env` files. The runtime must inject the variables. `.env.example` is a template for `docker run --env-file` (or compose); copy it to `.env` and replace the placeholders. Example values live there, not here.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes, unless `DJANGO_DEBUG` is on | none (startup fails) | Django secret key. An insecure development fallback exists only when `DJANGO_DEBUG` is on; never rely on it in production. |
| `DATABASE_URL` | No | SQLite `db.sqlite3` | Database URL, a Postgres URL. |
| `DJANGO_DEBUG` | No | off | `1`/`true`/`yes`/`on` enables debug. Leave off in production. |
| `DJANGO_ALLOWED_HOSTS` | Yes in production | empty | Comma-separated hostnames Django will serve. Empty with debug off means every request except the probes is rejected with 400. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | When behind TLS | empty | Comma-separated origins including scheme. |
| `DJANGO_TRUST_PROXY_PROTO` | Behind a TLS-terminating proxy | off | `1`/`true`/`yes`/`on` makes Django trust `X-Forwarded-Proto`. |
| `FORWARDED_ALLOW_IPS` | Behind a proxy | `127.0.0.1` | Proxy address(es)/CIDR whose forwarded headers uvicorn trusts. |
| `OPENSEARCH_URL` | No | `http://localhost:9200` | OpenSearch endpoint. If it is unreachable, search falls back to the database. |
| `WEB_CONCURRENCY` | No | `1` | Number of uvicorn worker processes (read by uvicorn). |

### Behind an ingress

Two settings are involved, and they act at different layers:

- `FORWARDED_ALLOW_IPS` (uvicorn; the image passes `--proxy-headers`): uvicorn only honours `X-Forwarded-*` headers from these addresses, default `127.0.0.1` only. Set it to the ingress/proxy address or CIDR so uvicorn applies the forwarded scheme and client IP. Otherwise the client IP is the proxy's.
- `DJANGO_TRUST_PROXY_PROTO=1` (Django): sets `SECURE_PROXY_SSL_HEADER` so Django itself reads `X-Forwarded-Proto` to decide a request is HTTPS. Django applies no source-IP check here, so only enable it when all traffic comes through a proxy that sets or strips that header.

Behind an ingress that terminates TLS, set both. Needs `DJANGO_CSRF_TRUSTED_ORIGINS` with the `https://` origin for CSRF checks on HTTPS.

## Probe endpoints

Both are answered by middleware before host validation, so probes addressed to the pod IP work without being listed in `DJANGO_ALLOWED_HOSTS`.

- `/healthz/` (liveness): returns `200 ok`. Has no dependencies, so it never fails because of the database or OpenSearch.
- `/functionalz/` (readiness): returns JSON such as `{"database": "up", "opensearch": "down"}`. Status is `503` only when the database is down. OpenSearch being down is reported in the body only and still returns `200`, because search degrades to a database fallback.

## One-off commands

Run these as Jobs (or `docker run` with a command override), never at container startup, so that multiple replicas do not race. Pass the same environment as the app (`.env` here means a copy of `.env.example` with real values) (`DATABASE_URL`, `OPENSEARCH_URL`, `SECRET_KEY`, ...).

```sh
docker run --rm --env-file .env locallibrary python manage.py migrate
docker run --rm --env-file .env locallibrary python manage.py search_index
```

- `migrate` applies database migrations. Because old and new pods run side by side during a rolling deploy, migrations must be backward-compatible with the previous release (e.g. add columns before using them, drop them in a later release).
- `search_index` rebuilds the OpenSearch indexes (`catalog-book`, `catalog-author`) from the database. It fails with a `CommandError` if OpenSearch is unreachable, so run it only once OpenSearch is up. Run it after the first deploy and whenever the index needs rebuilding.

## Deploying

For the human deployment checklist, see issue [#22](https://github.com/rvalenciano/locallibrary/issues/22).
