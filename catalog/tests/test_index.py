from django.test import TestCase

from catalog.models import Author, Book, Genre, Language
from catalog.search import index

from .fakes import FakeIndex


class IndexingSignalTests(TestCase):
    def setUp(self) -> None:
        self.index = FakeIndex()
        self.enterContext(index.use_index(self.index))

    def test_saving_a_book_indexes_its_document(self) -> None:
        author = Author.objects.create(first_name='Isaac', last_name='Asimov')
        language = Language.objects.create(name='English')
        book = Book.objects.create(
            title='Foundation', author=author, summary='Empire', isbn='1111111111111', language=language)

        self.assertEqual(self.index.documents[Book][book.pk], {
            'title': 'Foundation',
            'author': 'Asimov, Isaac',
            'summary': 'Empire',
            'isbn': '1111111111111',
            'genres': [],
            'language': 'English',
        })

    def test_deleting_a_book_removes_its_document(self) -> None:
        book = Book.objects.create(title='Foundation', summary='Empire', isbn='1111111111111')
        pk = book.pk

        book.delete()

        self.assertNotIn(pk, self.index.documents[Book])

    def test_deleting_an_author_removes_its_document(self) -> None:
        author = Author.objects.create(first_name='Isaac', last_name='Asimov')
        pk = author.pk

        author.delete()

        self.assertNotIn(pk, self.index.documents[Author])

    def test_saving_an_author_refreshes_their_books_documents(self) -> None:
        author = Author.objects.create(first_name='Isaac', last_name='Asimov')
        book = Book.objects.create(title='Foundation', author=author, summary='Empire', isbn='1111111111111')

        author.first_name = 'Isaak'
        author.save()

        self.assertEqual(self.index.documents[Author][author.pk], {'first_name': 'Isaak', 'last_name': 'Asimov'})
        self.assertEqual(self.index.documents[Book][book.pk]['author'], 'Asimov, Isaak')

    def test_adding_a_genre_to_a_book_refreshes_its_document(self) -> None:
        book = Book.objects.create(title='Foundation', summary='Empire', isbn='1111111111111')
        genre = Genre.objects.create(name='Science Fiction')

        book.genre.add(genre)

        self.assertEqual(self.index.documents[Book][book.pk]['genres'], ['Science Fiction'])

    def test_renaming_a_genre_refreshes_the_documents_of_its_books(self) -> None:
        genre = Genre.objects.create(name='Sci-fi')
        book = Book.objects.create(title='Foundation', summary='Empire', isbn='1111111111111')
        book.genre.add(genre)

        genre.name = 'Science Fiction'
        genre.save()

        self.assertEqual(self.index.documents[Book][book.pk]['genres'], ['Science Fiction'])

    def test_renaming_a_language_refreshes_the_documents_of_its_books(self) -> None:
        language = Language.objects.create(name='Spanish')
        book = Book.objects.create(title='Foundation', summary='Empire', isbn='1111111111111', language=language)

        language.name = 'Español'
        language.save()

        self.assertEqual(self.index.documents[Book][book.pk]['language'], 'Español')
