"""Checks that run.py fails loudly (non-zero + clear message) when a
prerequisite is missing, instead of passing falsely.

Run with: python3 e2e/test_prereqs.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUN = Path(__file__).resolve().parent / "run.py"
TOOLS = ("agent-browser", "docker", "uv")


def main() -> int:
    failed = False
    for missing in TOOLS:
        with tempfile.TemporaryDirectory() as shim:
            for tool in TOOLS:
                if tool != missing:
                    stub = Path(shim) / tool
                    stub.write_text("#!/bin/sh\nexit 0\n")
                    stub.chmod(0o755)
            result = subprocess.run(
                check=False,
                args=[sys.executable, str(RUN)],
                env={**os.environ, "PATH": shim},
                capture_output=True,
                text=True,
            )
        output = result.stdout + result.stderr
        if result.returncode != 0 and f"missing prerequisite: {missing}" in output:
            print(f"ok   missing {missing} -> exit {result.returncode}")
        else:
            print(f"FAIL missing {missing} -> exit {result.returncode}: {output}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
