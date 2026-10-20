from typing import Any

from django.db.models import Model
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from . import search
from .models import Author, Book, Genre, Language


@receiver(post_save, sender=Book)
@receiver(post_save, sender=Author)
def document_saved(sender: type[Model], instance: Book | Author, **kwargs: Any) -> None:
    search.index_document(instance)


@receiver(post_delete, sender=Book)
@receiver(post_delete, sender=Author)
def document_deleted(sender: type[Model], instance: Book | Author, **kwargs: Any) -> None:
    search.delete_document(instance)


@receiver(m2m_changed, sender=Book.genre.through)
def book_genres_changed(sender: type[Model], instance: Model, action: str, **kwargs: Any) -> None:
    # The admin saves a Book first and its genres afterwards, so re-index once the links change.
    if action in {"post_add", "post_remove", "post_clear"} and isinstance(instance, Book):
        search.index_document(instance)


@receiver(post_save, sender=Author)
@receiver(post_save, sender=Genre)
@receiver(post_save, sender=Language)
def related_saved(sender: type[Model], instance: Author | Genre | Language, **kwargs: Any) -> None:
    # Book documents embed the names of their author, genres and language.
    # The stubs only know reverse accessors through the mypy plugin, which basedpyright does not run.
    for book in instance.book_set.all():  # pyright: ignore[reportAttributeAccessIssue]
        search.index_document(book)
