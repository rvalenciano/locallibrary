"""Browse: books pagination, and book and author detail pages reached by links."""

from harness import AssertionFailure, Browser

BOOK_LINKS = 'ul li a[href*="/book/"]'
AUTHOR_LINKS = 'ul li a[href*="/authors/"]:not([href$="/authors/"])'
PAGE_SIZE = 10


def scenario(browser: Browser) -> None:
    browser.open("/catalog/books/")
    first_page = browser.link_texts(BOOK_LINKS)
    if len(first_page) != PAGE_SIZE:
        raise AssertionFailure(
            f"{PAGE_SIZE} books on page 1", f"{len(first_page)}: {first_page}"
        )

    browser.click(".page-links a")
    browser.assert_contains(browser.url(), "page=2")
    second_page = browser.link_texts(BOOK_LINKS)
    if not second_page or set(second_page) & set(first_page):
        raise AssertionFailure("page 2 lists books not on page 1", f"{second_page}")

    # Book detail, reached from the list: title and author are shown.
    entry = browser.eval_json(
        f"(() => {{ const a = document.querySelector({BOOK_LINKS!r}); "
        "return a.closest('li').textContent.replace(/\\s+/g, ' ').trim(); })()"
    )
    title = second_page[0]
    browser.click(BOOK_LINKS)
    browser.assert_contains(browser.heading(), title)
    text = browser.text()
    browser.assert_contains(text, "Author:")
    author = str(entry).removeprefix(title).strip().strip("()")
    browser.assert_contains(text, author)

    # Author detail, reached from the author list: the name is the heading.
    browser.open("/catalog/authors/")
    name = browser.link_texts(AUTHOR_LINKS)[0]
    browser.click(AUTHOR_LINKS)
    last, first = name.split(", ", 1)
    heading = browser.heading()
    if heading != f"{first} {last}":
        raise AssertionFailure(f'author heading "{first} {last}"', heading)
