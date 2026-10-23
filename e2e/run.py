"""Browser smoke tests for the running site. See e2e/README.md."""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def main() -> int:
    try:
        with harness.environment() as browser:
            for path in sorted(SCENARIOS_DIR.glob("*.py")):
                harness.log(f"scenario: {path.stem}")
                spec = importlib.util.spec_from_file_location(path.stem, path)
                assert spec and spec.loader
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                try:
                    module.scenario(browser)
                except harness.AssertionFailure as failure:
                    print(f"[e2e] FAIL scenario: {path.stem}", file=sys.stderr)
                    print(f"[e2e]   expected: {failure.expected}", file=sys.stderr)
                    print(f"[e2e]   seen:     {failure.seen}", file=sys.stderr)
                    return 1
    except harness.SetupError as error:
        print(f"[e2e] ERROR: {error}", file=sys.stderr)
        return 1
    harness.log("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
