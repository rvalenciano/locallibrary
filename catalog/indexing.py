"""Keeps the search index in step with the database.

This module decides which documents a change makes stale and how to write them.
Signal receivers only report changes; `search` only reads.
"""
import logging
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from django.db.models import Model, QuerySet
from opensearchpy import helpers
from opensearchpy.exceptions import OpenSearchException

from . import search
from .models import Author, Book, Genre, Language

logger = logging.getLogger(__name__)

Document = dict[str, Any]


class Index(Protocol):
    """Where documents are written. OpenSearch in production, an in-memory fake in tests."""

    def recreate(self, model: type[Model]) -> None: ...

    def write(self, model: type[Model], documents: Iterable[tuple[int, Document]]) -> int: ...

    def delete(self, model: type[Model], pk: int) -> None: ...


class OpenSearchIndex:
    def recreate(self, model: type[Model]) -> None:
        client = search.get_client()
        client.indices.delete(index=search.index_name(model), ignore_unavailable=True)  # pyright: ignore[reportCallIssue]  # stub omits query params
        client.indices.create(index=search.index_name(model))

    def write(self, model: type[Model], documents: Iterable[tuple[int, Document]]) -> int:
        actions = ({"_index": search.index_name(model), "_id": pk, "_source": document} for pk, document in documents)
        written, _ = helpers.bulk(search.get_client(), actions, refresh=True)
        return written

    def delete(self, model: type[Model], pk: int) -> None:
        search.get_client().delete(index=search.index_name(model), id=pk, refresh=True, ignore=[404])  # pyright: ignore[reportCallIssue]  # stub omits query params


_index: Index = OpenSearchIndex()


@contextmanager
def use_index(index: Index) -> Iterator[Index]:
    """Swap the index for the duration of the block."""
    global _index
    previous, _index = _index, index
    try:
        yield index
    finally:
        _index = previous


def _book_document(book: Book) -> Document:
    return {
        "title": book.title,
        "author": str(book.author) if book.author else "",
        "summary": book.summary,
        "isbn": book.isbn,
        "genres": [genre.name for genre in book.genre.all()],
        "language": book.language.name if book.language else "",
    }


def _author_document(author: Author) -> Document:
    return {"first_name": author.first_name, "last_name": author.last_name}


DOCUMENTS: dict[type[Model], Callable[[Any], Document]] = {
    Book: _book_document,
    Author: _author_document,
}


def _books() -> QuerySet[Book]:
    return Book.objects.select_related("author", "language").prefetch_related("genre")


# Book documents embed the names of these related rows, so changing one makes its books stale.
BOOK_RELATIONS: dict[type[Model], str] = {Author: "author", Genre: "genre", Language: "language"}


def _stale(obj: Model) -> dict[type[Model], list[Model]]:
    """Every row whose document no longer matches the database after `obj` changed."""
    model = type(obj)
    stale: dict[type[Model], list[Model]] = {}
    if model in DOCUMENTS:
        stale[model] = [obj]
    if model in BOOK_RELATIONS:
        stale.setdefault(Book, []).extend(_books().filter(**{BOOK_RELATIONS[model]: obj}))
    return stale


def update(obj: Model) -> None:
    """Write the documents made stale by a change to `obj`, one batch per index.

    Never raises: a search outage must not break saves.
    """
    for model, rows in _stale(obj).items():
        try:
            _index.write(model, [(row.pk, DOCUMENTS[model](row)) for row in rows])
        except OpenSearchException:
            logger.warning("Could not index %s documents for %r in OpenSearch", model.__name__, obj, exc_info=True)


def remove(obj: Model) -> None:
    """Drop `obj`'s document. Never raises, for the same reason as `update`."""
    try:
        _index.delete(type(obj), obj.pk)
    except OpenSearchException:
        logger.warning("Could not delete %r from OpenSearch", obj, exc_info=True)


def rebuild(model: type[Model]) -> int:
    """Drop and recreate the model's index, then write every row. Returns the count.

    Unlike `update`, this raises when the cluster is unreachable so the caller can report it.
    """
    rows = _books() if model is Book else model._default_manager.all()
    _index.recreate(model)
    return _index.write(model, ((row.pk, DOCUMENTS[model](row)) for row in rows.iterator(chunk_size=500)))
