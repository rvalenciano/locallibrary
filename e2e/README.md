# E2E smoke tests

Drives the running site in a real browser with `agent-browser`.

The harness is stdlib-only Python (no extra dependencies).

Prerequisites: `agent-browser`, Docker (daemon running), `uv`. The script fails
loudly if any is missing.

Run from anywhere:

    python3 e2e/run.py

It starts OpenSearch (`docker compose up -d opensearch`, left running), builds a
temporary SQLite database via `DATABASE_PATH`, runs `migrate`, `seed --reset`
and `search_index`, starts the dev server on a free port, runs every scenario,
then removes the server, browser session and temp files (also on failure).
Your `db.sqlite3` is never touched. Note that `search_index` rebuilds the shared
OpenSearch indexes from the temporary data.

The first failed assertion prints the scenario name, expected and seen text,
and exits non-zero.

## Adding a scenario

Create `e2e/scenarios/NN_name.py` defining `scenario(browser)` (helpers are on
`Browser` in `harness.py`: `open`, `text`, `assert_contains`,
`assert_not_contains`, `assert_match`). The runner loads files in name order. One file per scenario means
parallel branches do not conflict. Numbering: 10 home, 20 browse, 30 search,
40 fallback.

`python3 e2e/test_prereqs.py` checks that missing prerequisites are reported.
