from collections.abc import Iterable
from typing import Any

from django.db.models import Model


class FakeIndex:
    """In-memory stand-in for the search index: lets tests see what was written without a cluster."""

    def __init__(self) -> None:
        self.documents: dict[type[Model], dict[int, dict[str, Any]]] = {}

    def recreate(self, model: type[Model]) -> None:
        self.documents[model] = {}

    def write(self, model: type[Model], documents: Iterable[tuple[int, dict[str, Any]]]) -> int:
        stored = self.documents.setdefault(model, {})
        count = 0
        for pk, document in documents:
            stored[pk] = document
            count += 1
        return count

    def delete(self, model: type[Model], pk: int) -> None:
        self.documents.get(model, {}).pop(pk, None)
