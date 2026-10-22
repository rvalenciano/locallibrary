from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = 'catalog'

    def ready(self) -> None:
        from . import signals  # noqa: F401  (registers the OpenSearch signal handlers)
