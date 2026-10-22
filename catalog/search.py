"""OpenSearch integration for the catalog.

The database stays the source of truth; OpenSearch holds a searchable copy of
each Book and Author. Indexes use OpenSearch's dynamic mapping, so every string
field in a document is searchable without declaring a schema.
"""
import logging
from collections.abc import Callable
from functools import cache, reduce
from operator import or_
from typing import Any

from django.conf import settings
from django.db.models import Model, Q, QuerySet
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

from .models import Author, Book

logger = logging.getLogger(__name__)


def _book_document(book: Book) -> dict[str, Any]:
    return {
        "title": book.title,
        "author": str(book.author) if book.author else "",
        "summary": book.summary,
        "isbn": book.isbn,
        "genres": [genre.name for genre in book.genre.all()],
        "language": book.language.name if book.language else "",
    }


def _author_document(author: Author) -> dict[str, Any]:
    return {"first_name": author.first_name, "last_name": author.last_name}


# model -> (queryset used for full rebuilds, function that turns one row into a document)
SEARCHABLE: dict[type[Model], tuple[QuerySet[Any], Callable[[Any], dict[str, Any]]]] = {
    Book: (Book.objects.select_related("author", "language").prefetch_related("genre"), _book_document),
    Author: (Author.objects.all(), _author_document),
}


@cache
def get_client() -> OpenSearch:
    return OpenSearch(hosts=[settings.OPENSEARCH_URL], timeout=5)


@cache
def get_ping_client() -> OpenSearch:
    """A separate client for health probes: short timeout, no retries, so a blackholed cluster
    cannot make a probe slower than the kubelet's own timeout."""
    return OpenSearch(hosts=[settings.OPENSEARCH_URL], timeout=1, max_retries=0)


def is_up() -> bool:
    """Whether the cluster answers a ping. Never raises."""
    try:
        return bool(get_ping_client().ping())
    except OpenSearchException:
        return False


def index_name(model: type[Model]) -> str:
    return f"catalog-{model._meta.model_name}"


def rebuild_index(model: type[Model]) -> int:
    """Drop and recreate the model's index, then bulk-load every row. Returns the count."""
    queryset, to_document = SEARCHABLE[model]
    client = get_client()
    client.indices.delete(index=index_name(model), ignore_unavailable=True)  # pyright: ignore[reportCallIssue]  # stub omits query params
    client.indices.create(index=index_name(model))
    actions = (
        {"_index": index_name(model), "_id": obj.pk, "_source": to_document(obj)}
        for obj in queryset.all().iterator(chunk_size=500)
    )
    indexed, _ = helpers.bulk(client, actions)
    client.indices.refresh(index=index_name(model))
    return indexed


def index_document(obj: Model) -> None:
    """Index (or re-index) one row. Never raises: a search outage must not break saves."""
    _, to_document = SEARCHABLE[type(obj)]
    try:
        get_client().index(index=index_name(type(obj)), id=obj.pk, body=to_document(obj), refresh=True)  # pyright: ignore[reportCallIssue]
    except OpenSearchException:
        logger.warning("Could not index %r in OpenSearch", obj, exc_info=True)


def delete_document(obj: Model) -> None:
    try:
        get_client().delete(index=index_name(type(obj)), id=obj.pk, refresh=True, ignore=[404])  # pyright: ignore[reportCallIssue]
    except OpenSearchException:
        logger.warning("Could not delete %r from OpenSearch", obj, exc_info=True)


def search_ids(model: type[Model], query: str, size: int = 10_000) -> list[int]:
    """Return primary keys of rows matching `query` in any field, best match first.

    10,000 is OpenSearch's default result window. Raises OpenSearchException if the cluster is unreachable.
    """
    body = {
        "size": size,
        "_source": False,
        "query": {"multi_match": {"query": query, "fields": ["*"], "fuzziness": "AUTO"}},
    }
    response = get_client().search(index=index_name(model), body=body)
    return [int(hit["_id"]) for hit in response["hits"]["hits"]]


FALLBACK_FIELDS: dict[type[Model], tuple[str, ...]] = {
    Book: ("title", "summary", "isbn", "author__first_name", "author__last_name", "genre__name", "language__name"),
    Author: ("first_name", "last_name"),
}

def fallback_queryset(model: type[Model], queryset: QuerySet, query: str) -> QuerySet[Book|Author]:
    """Database-only search for when OpenSearch is down: every term must match some field.

    There is no relevance ranking or typo tolerance here, so rows keep the view's ordering.
    """
    for term in query.split():
        queryset = queryset.filter(reduce(or_, (Q(**{f"{field}__icontains": term}) for field in FALLBACK_FIELDS[model])))
    return queryset.distinct()
