# Session log: seeding 100 more books

Skills run while extending the `seed` management command, and what each produced. Work went from idea to merged PR ([#9](https://github.com/rvalenciano/locallibrary/pull/9)).

## 1. `grill-me` (calls `grilling`)

**Input:** "I want to add 100 books in the custom command to seed the app."

**What it did:** Four rounds of numbered questions, each with a recommended answer, until no open decisions remained.

**Result:** the design decisions:
- 100 additional real books, 107 in total, with about 14 new real authors (19 in total).
- Keep the existing 5 genres.
- English and Spanish only, with a real one-line summary per book.
- Fixed, pre-generated ISBNs stored in the data. No Faker at runtime.
- Books looked up by (title, author), so re-runs stay idempotent.
- Copies per book `1 + pk % 5`, with the status logic unchanged.
- No `--count` option and no tests.
- Index through the existing signals and fail fast if OpenSearch is unreachable.

## 2. `to-spec`

**What it did:** Turned the grilling outcome into a spec, with no new interview.

**Result:** GitHub issue [#1](https://github.com/rvalenciano/locallibrary/issues/1) ("Seed 100 more real books with authors and copies"), labelled `ready-for-agent`. It holds the problem statement, 18 user stories, implementation decisions, testing decisions (none to be written, seam noted as `call_command("seed")`) and out-of-scope items.

## 3. `to-tickets`

**What it did:** Split the spec into vertical slices with blocking edges, which the user approved.

**Result:** sub-issues of #1, all `ready-for-agent`:

| Issue | Ticket | Blocked by |
|---|---|---|
| #2 | Dedupe seeded books by title and author | none |
| #3 | Vary the number of copies per seeded book | none |
| #4 | Fail with a clear error when OpenSearch is unreachable | none |
| #5 | Seed sci-fi and fantasy authors and books | #2 |
| #6 | Seed classic, mystery and poetry authors and books | #2 |
| #7 | Seed Spanish-language authors and books | #2 |
| #8 | Verify the full seed | #3, #4, #5, #6, #7 |

## 4. `implement-spec` (run five times)

Branch: `seed-100-books`. The user committed the work, so no commits were made by the agent.

| Run | Tickets | Result |
|---|---|---|
| 1 | #2, #3 | Books are looked up by (title, author) with ISBN, summary and language as defaults. Copies per book are `1 + pk % 5`. A second run reported "0 new". |
| 2 | #4 | `seed` pings OpenSearch before any write. If unreachable it raises a `CommandError` pointing to `docker compose up -d` and `search_index`, and the database is unchanged. Checked against a dead port with a byte-identical DB backup. |
| 3 | #5 | 5 authors (Tolkien, Herbert, Dick, Bradbury, Pratchett) and 37 English books. Fixed fake ISBNs `97851…`. |
| 4 | #6, #7 | #6: 6 authors and 48 English books (48, not 50, so the total stays at 100). #7: 3 authors and 15 Spanish books. ISBNs `97852…` and `97853…`. |
| 5 | #8 | Verification only, no code changes (details below). |

### Verification (ticket #8)

After `seed --reset`, a second `seed`, a `search_index` rebuild and a third `seed`:

- 107 books, 19 authors, 5 genres, 3 languages, 318 copies.
- Re-runs added nothing.
- 107 unique 13-character ISBNs, and no duplicate (title, author) pairs.
- 91 English and 16 Spanish books (15 new plus *Cien años de soledad*).
- 1 to 5 copies per book. Every loaned copy has a due date and no other copy does.
- OpenSearch holds 107 books and 19 authors. Searches for Dune, Quijote, Ficciones and Poirot return results. "cólera" and the unaccented "Garcia Marquez" also match.

## 5. Wrap-up

- Issues #1 to #8 closed as completed.
- PR #9 opened against `main` and merged by the user.

## Notes

- A `sed -i` mistake in run 1 let the seed commands run against the real `db.sqlite3` (git-ignored). `seed --reset` rebuilds it.
- The unrelated `paginate_by = 10` change in `catalog/views.py` was never part of this work.
- Signing commits with GPG failed in this environment (no tty for pinentry). The user then chose to make the commits themselves.
