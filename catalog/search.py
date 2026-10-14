"""OpenSearch integration for the catalog.

The database stays the source of truth; OpenSearch holds a searchable copy of
each Book and Author. Indexes use OpenSearch's dynamic mapping, so every string
field in a document is searchable without declaring a schema.
"""
import logging
from functools import cache

from django.conf import settings
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

from .models import Author, Book

logger = logging.getLogger(__name__)


def _book_document(book):
    return {
        "title": book.title,
        "author": str(book.author) if book.author else "",
        "summary": book.summary,
        "isbn": book.isbn,
        "genres": [genre.name for genre in book.genre.all()],
        "language": book.language.name if book.language else "",
    }


def _author_document(author):
    return {"first_name": author.first_name, "last_name": author.last_name}


# model -> (queryset used for full rebuilds, function that turns one row into a document)
SEARCHABLE = {
    Book: (Book.objects.select_related("author", "language").prefetch_related("genre"), _book_document),
    Author: (Author.objects.all(), _author_document),
}


@cache
def get_client() -> OpenSearch:
    return OpenSearch(hosts=[settings.OPENSEARCH_URL], timeout=5)


def index_name(model) -> str:
    return f"catalog-{model._meta.model_name}"


def rebuild_index(model) -> int:
    """Drop and recreate the model's index, then bulk-load every row. Returns the count."""
    queryset, to_document = SEARCHABLE[model]
    client = get_client()
    client.indices.delete(index=index_name(model), ignore_unavailable=True)
    client.indices.create(index=index_name(model))
    actions = (
        {"_index": index_name(model), "_id": obj.pk, "_source": to_document(obj)}
        for obj in queryset.all().iterator(chunk_size=500)
    )
    indexed, _ = helpers.bulk(client, actions)
    client.indices.refresh(index=index_name(model))
    return indexed


def index_document(obj) -> None:
    """Index (or re-index) one row. Never raises: a search outage must not break saves."""
    _, to_document = SEARCHABLE[type(obj)]
    try:
        get_client().index(index=index_name(type(obj)), id=obj.pk, body=to_document(obj), refresh=True)
    except OpenSearchException:
        logger.warning("Could not index %r in OpenSearch", obj, exc_info=True)


def delete_document(obj) -> None:
    try:
        get_client().delete(index=index_name(type(obj)), id=obj.pk, refresh=True, ignore=[404])
    except OpenSearchException:
        logger.warning("Could not delete %r from OpenSearch", obj, exc_info=True)


def search_ids(model, query: str, size: int = 10_000) -> list[int]:
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
