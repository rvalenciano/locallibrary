"""OpenSearch integration for the catalog.

The database stays the source of truth; OpenSearch holds a searchable copy of
each Book and Author. Indexes use OpenSearch's dynamic mapping, so every string
field in a document is searchable without declaring a schema. This module reads;
`index` writes.
"""
from functools import cache, reduce
from operator import or_

from django.conf import settings
from django.db.models import Model, Q, QuerySet
from opensearchpy import OpenSearch

from ..models import Author, Book


@cache
def get_client() -> OpenSearch:
    return OpenSearch(hosts=[settings.OPENSEARCH_URL], timeout=5)


def index_name(model: type[Model]) -> str:
    return f"catalog-{model._meta.model_name}"


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
