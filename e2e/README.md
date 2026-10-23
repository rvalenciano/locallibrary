# E2E smoke tests

Drives the running site in a real browser with `agent-browser`, as a safety net
for refactors. The harness is stdlib-only Python (no extra dependencies).

## Prerequisites

- `agent-browser`
- Docker, with the daemon running
- `uv`

The run fails loudly with a clear message if any of them is missing.

## Run

From the repo root:

    python3 e2e/run.py

It starts OpenSearch if needed (`docker compose up -d opensearch`, left running),
builds a temporary SQLite database via `DATABASE_PATH`, runs `migrate`,
`seed --reset` and `search_index`, starts the dev server on a free port, runs
every scenario in name order, then removes the server, browser session and temp
files, on pass or fail. It prints `[e2e] PASS` and exits 0, or on the first
failed assertion prints the scenario name, what was expected and what was seen,
and exits non-zero. Your `db.sqlite3` is never touched.

## Scenarios

| File | Checks |
| --- | --- |
| `10_home.py` | home page shows non-zero book, copy and author counts |
| `20_browse.py` | 10 books per page, next-page link, book and author detail pages |
| `30_search.py` | search ranking, typo tolerance, authors search, no-match message |
| `40_fallback.py` | with OpenSearch stopped, search falls back to the database |

## Things to know

- `search_index` rebuilds the shared OpenSearch indexes from the temporary
  data, so rebuild them from your own data afterwards if you use the dev site.
- `40_fallback.py` stops the shared `locallibrary-opensearch` container for a
  few seconds and always restarts it. Don't run the suite while another process
  is using that container.

## Adding a scenario

Create `e2e/scenarios/NN_name.py` defining `scenario(browser)`. The runner loads
files in name order, and one file per scenario means parallel branches do not
conflict. Helpers on `Browser` in `harness.py`: `open`, `click`, `fill`, `text`,
`heading`, `url`, `wait_for_url`, `link_texts`, `eval_json`, `assert_contains`,
`assert_not_contains` and `assert_match`. Raise `AssertionFailure(expected, seen)`
for a custom check.

`python3 e2e/test_prereqs.py` checks that missing prerequisites are reported.
