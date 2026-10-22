#!/usr/bin/env bash
# Smoke-test a built image: run it production-style and check external behaviour.
# Usage: smoke-test.sh <image>
set -euo pipefail

image="${1:?usage: smoke-test.sh <image>}"
name="smoke-$$"
port="${SMOKE_PORT:-8000}"
base="http://localhost:${port}"

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "::group::docker logs"
    docker logs "$name" 2>&1 || true
    echo "::endgroup::"
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

# DJANGO_DEBUG is not passed: the image pins DJANGO_DEBUG=0, so DEBUG is off.
docker run -d --name "$name" -p "${port}:8000" \
  -e SECRET_KEY=ci-smoke-test-key \
  -e DJANGO_ALLOWED_HOSTS=localhost \
  "$image" >/dev/null

echo "Waiting for readiness..."
ready=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 -o /dev/null "${base}/healthz/" 2>/dev/null; then
    ready=1
    break
  fi
  running=$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || echo missing)
  if [ "$running" != "true" ]; then
    echo "Container is not running (state: ${running}) before becoming ready" >&2
    exit 1
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "Timed out waiting for /healthz/" >&2
  exit 1
fi

# Usage: check_status <path> [extra curl header, e.g. 'Host: other.example']
check_status() {
  local path="$1" header="${2:-}" code label="$1"
  local args=()
  if [ -n "$header" ]; then
    args=(-H "$header")
    label="${path} with header '${header}'"
  fi
  code=$(curl -s --max-time 5 -o /dev/null -w '%{http_code}' ${args[@]+"${args[@]}"} "${base}${path}" || true)
  if [ "$code" != "200" ]; then
    echo "FAIL ${label}: expected 200, got ${code}" >&2
    exit 1
  fi
  echo "ok ${label} -> 200"
}

check_status /healthz/
check_status /static/css/styles.css
# Probes must answer before host validation (kubelet probes use the pod IP as Host).
check_status /healthz/ 'Host: not-allowed.example'

# Readiness: the database must be up. OpenSearch is expected to be down here and must not matter.
body=$(curl -s --max-time 10 -w '\n%{http_code}' "${base}/functionalz/" || true)
code="${body##*$'\n'}"
body="${body%$'\n'*}"
if [ "$code" != "200" ] || ! printf '%s' "$body" | grep -Eq '"database": *"up"'; then
  echo "FAIL /functionalz/: expected 200 with database up, got ${code}: ${body}" >&2
  exit 1
fi
echo "ok /functionalz/ -> 200 ${body}"

uid=$(docker exec "$name" id -u)
if [ "$uid" = "0" ]; then
  echo "FAIL: container process runs as root" >&2
  exit 1
fi
echo "ok uid=${uid} (not root)"
