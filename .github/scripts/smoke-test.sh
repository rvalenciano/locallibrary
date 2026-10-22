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

# DJANGO_DEBUG is intentionally unset so DEBUG is off.
docker run -d --name "$name" -p "${port}:8000" \
  -e SECRET_KEY=ci-smoke-test-key \
  -e DJANGO_ALLOWED_HOSTS=localhost \
  "$image" >/dev/null

echo "Waiting for readiness..."
ready=0
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "${base}/healthz/" 2>/dev/null; then
    ready=1
    break
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$name")" != "true" ]; then
    echo "Container exited before becoming ready" >&2
    exit 1
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "Timed out waiting for /healthz/" >&2
  exit 1
fi

check_status() {
  local path="$1" code
  code=$(curl -s -o /dev/null -w '%{http_code}' "${base}${path}")
  if [ "$code" != "200" ]; then
    echo "FAIL ${path}: expected 200, got ${code}" >&2
    exit 1
  fi
  echo "ok ${path} -> 200"
}

check_status /healthz/
check_status /static/css/styles.css

uid=$(docker exec "$name" id -u)
if [ "$uid" = "0" ]; then
  echo "FAIL: container process runs as root" >&2
  exit 1
fi
echo "ok uid=${uid} (not root)"
