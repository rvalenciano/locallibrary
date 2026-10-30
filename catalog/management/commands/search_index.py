from typing import Any

from django.core.management.base import BaseCommand, CommandError
from opensearchpy.exceptions import OpenSearchException

from catalog.search import index


class Command(BaseCommand):
    help = "Drop and rebuild the OpenSearch indexes from the database."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            for model in index.DOCUMENTS:
                count = index.rebuild(model)
                self.stdout.write(self.style.SUCCESS(f"Indexed {count} {model._meta.verbose_name_plural}."))
        except OpenSearchException as exc:
            raise CommandError(f"Could not reach OpenSearch. Is `docker compose up -d` running? ({exc})") from exc
