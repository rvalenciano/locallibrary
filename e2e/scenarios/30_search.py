"""Search with OpenSearch up: ranking, typo tolerance, authors and no-match."""

from harness import AssertionFailure, Browser

BOOK_LINKS = 'ul li a[href*="/book/"]'
AUTHOR_LINKS = 'ul li a[href*="/authors/"]:not([href$="/authors/"])'
DEGRADED_NOTICE = "Search is temporarily unavailable"


def search(browser: Browser, path: str, query: str) -> str:
    """Submit the page's search form and return the resulting page text."""
    browser.open(path)
    browser.fill('input[name="q"]', query)
    browser.click('button[type="submit"]')
    browser.wait_for_url("**q=**")
    text = browser.text()
    browser.assert_not_contains(text, DEGRADED_NOTICE)
    return text


def scenario(browser: Browser) -> None:
    search(browser, "/catalog/books/", "robot")
    books = browser.link_texts(BOOK_LINKS)
    if not books or books[0] != "I, Robot":
        raise AssertionFailure('"I, Robot" as the first result for "robot"', f"{books}")

    # The database fallback has no typo tolerance, so this proves OpenSearch is live.
    search(browser, "/catalog/books/", "foundaton")
    books = browser.link_texts(BOOK_LINKS)
    if "Foundation" not in books:
        raise AssertionFailure(
            'a result titled "Foundation" for "foundaton"', f"{books}"
        )

    search(browser, "/catalog/authors/", "ursula")
    authors = browser.link_texts(AUTHOR_LINKS)
    if not any("Le Guin" in name for name in authors):
        raise AssertionFailure('Le Guin among results for "ursula"', f"{authors}")

    text = search(browser, "/catalog/books/", "zzqxjvkw")
    browser.assert_contains(text, "No books match your search.")
