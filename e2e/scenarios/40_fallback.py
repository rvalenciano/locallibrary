"""Fallback: with OpenSearch down, search still answers from the database."""

import harness
from harness import AssertionFailure, Browser

BOOK_LINKS = 'ul li a[href*="/book/"]'
DEGRADED_NOTICE = "Search is temporarily unavailable"


def scenario(browser: Browser) -> None:
    # The container is restarted when the block exits, even if a check fails.
    with harness.opensearch_stopped():
        browser.open("/catalog/books/")
        browser.fill('input[name="q"]', "foundation")
        browser.click('button[type="submit"]')
        browser.wait_for_url("**q=**")
        books = browser.link_texts(BOOK_LINKS)
        if "Foundation" not in books:
            raise AssertionFailure(
                'a result titled "Foundation" from the database', f"{books}"
            )
        browser.assert_contains(browser.text(), DEGRADED_NOTICE)
