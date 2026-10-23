"""Environment and helpers for the e2e smoke harness. See e2e/README.md."""

import contextlib
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENSEARCH_HEALTH_URL = os.environ.get(
    "OPENSEARCH_HEALTH_URL", "http://localhost:9200/_cluster/health"
)
OPENSEARCH_CONTAINER = "locallibrary-opensearch"
PREREQUISITES = ("agent-browser", "docker", "uv")


class SetupError(Exception):
    """The environment could not be prepared; not an assertion failure."""


class AssertionFailure(Exception):
    def __init__(self, expected: str, seen: str) -> None:
        super().__init__(expected)
        self.expected = expected
        self.seen = " ".join(seen.split())[:400]


def log(message: str) -> None:
    print(f"[e2e] {message}", flush=True)


def check_prereqs() -> None:
    for tool in PREREQUISITES:
        if shutil.which(tool) is None:
            raise SetupError(f"missing prerequisite: {tool} (install it and re-run)")
    if (
        subprocess.run(
            check=False, args=["docker", "info"], capture_output=True
        ).returncode
        != 0
    ):
        raise SetupError("Docker is installed but its daemon is not running")


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except urllib.error.URLError, OSError:
        return False


def start_opensearch() -> None:
    if _healthy(OPENSEARCH_HEALTH_URL):
        log("OpenSearch already running")
        return
    log("starting OpenSearch")
    # The container name is fixed, so a container created from another checkout
    # (different compose project) must be started directly, not re-created.
    exists = (
        subprocess.run(
            check=False,
            args=["docker", "container", "inspect", OPENSEARCH_CONTAINER],
            capture_output=True,
        ).returncode
        == 0
    )
    command = (
        ["docker", "start", OPENSEARCH_CONTAINER]
        if exists
        else ["docker", "compose", "up", "-d", "opensearch"]
    )
    if (
        subprocess.run(
            check=False, args=command, cwd=REPO_ROOT, capture_output=True
        ).returncode
        != 0
    ):
        raise SetupError(f"`{' '.join(command)}` failed")
    for _ in range(60):
        if _healthy(OPENSEARCH_HEALTH_URL):
            return
        time.sleep(2)
    raise SetupError("OpenSearch did not become healthy within 120s")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _manage(*args: str) -> None:
    result = subprocess.run(
        check=False,
        args=["uv", "run", "python", "manage.py", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SetupError(f"manage.py {' '.join(args)} failed:\n{result.stderr}")


class Browser:
    """Thin wrapper over the agent-browser CLI, bound to the site's base URL."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def open(self, path: str) -> None:
        result = subprocess.run(
            check=False,
            args=["agent-browser", "open", self.base_url + path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionFailure(f"page {path} opens", result.stderr or result.stdout)

    def text(self) -> str:
        result = subprocess.run(
            check=False,
            args=["agent-browser", "get", "text", "body"],
            capture_output=True,
            text=True,
        )
        return result.stdout

    def assert_contains(self, text: str, expected: str) -> None:
        if expected not in text:
            raise AssertionFailure(f'page contains "{expected}"', text)

    def assert_not_contains(self, text: str, unexpected: str) -> None:
        if unexpected in text:
            raise AssertionFailure(f'page does not contain "{unexpected}"', text)

    def assert_match(self, text: str, pattern: str, description: str) -> None:
        if not re.search(pattern, text):
            raise AssertionFailure(description, text)


@contextlib.contextmanager
def environment() -> Iterator[Browser]:
    """Bring up OpenSearch, a throwaway database and a dev server; tear down on exit."""
    check_prereqs()
    os.environ["AGENT_BROWSER_SESSION"] = f"locallibrary-e2e-{os.getpid()}"
    server: subprocess.Popen[bytes] | None = None
    tmp_dir = Path(tempfile.mkdtemp(prefix="locallibrary-e2e-"))
    try:
        start_opensearch()
        os.environ["DATABASE_PATH"] = str(tmp_dir / "e2e.sqlite3")
        log(f"temporary database: {os.environ['DATABASE_PATH']}")
        _manage("migrate", "--noinput")
        _manage("seed", "--reset")
        _manage("search_index")

        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        log(f"starting dev server on {base_url}")
        server_log = (tmp_dir / "server.log").open("wb")
        server = subprocess.Popen(
            [
                "uv",
                "run",
                "python",
                "manage.py",
                "runserver",
                f"127.0.0.1:{port}",
                "--noreload",
            ],
            cwd=REPO_ROOT,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        for _ in range(30):
            if server.poll() is not None or _healthy(base_url + "/"):
                break
            time.sleep(1)
        if server.poll() is not None or not _healthy(base_url + "/"):
            print((tmp_dir / "server.log").read_text(), file=sys.stderr)
            raise SetupError("dev server did not start")
        yield Browser(base_url)
    finally:
        subprocess.run(
            check=False, args=["agent-browser", "close"], capture_output=True
        )
        if server is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(server.pid, signal.SIGTERM)
            with contextlib.suppress(subprocess.TimeoutExpired):
                server.wait(timeout=10)
        shutil.rmtree(tmp_dir, ignore_errors=True)
