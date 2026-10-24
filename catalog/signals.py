from typing import Any

from django.db.models import Model
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from . import index_sync
from .models import Author, Book, Genre, Language


@receiver(post_save, sender=Book)
@receiver(post_save, sender=Author)
@receiver(post_save, sender=Genre)
@receiver(post_save, sender=Language)
def row_saved(sender: type[Model], instance: Model, **kwargs: Any) -> None:
    index_sync.sync(instance)


@receiver(post_delete, sender=Book)
@receiver(post_delete, sender=Author)
def row_deleted(sender: type[Model], instance: Model, **kwargs: Any) -> None:
    index_sync.remove(instance)


@receiver(m2m_changed, sender=Book.genre.through)
def book_genres_changed(sender: type[Model], instance: Model, action: str, **kwargs: Any) -> None:
    # The admin saves a Book first and its genres afterwards, so re-index once the links change.
    if action in {"post_add", "post_remove", "post_clear"} and isinstance(instance, Book):
        index_sync.sync(instance)
