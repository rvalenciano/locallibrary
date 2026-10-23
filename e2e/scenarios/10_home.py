"""Home page loads with non-zero counts of books, copies and authors."""

from harness import Browser


def scenario(browser: Browser) -> None:
    browser.open("/")
    text = browser.text()
    browser.assert_contains(text, "Local Library Home")
    for label in ("Books", "Copies", "Authors"):
        browser.assert_match(
            text, rf"{label}: *[1-9][0-9]*", f"non-zero {label} count on the home page"
        )
