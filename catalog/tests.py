from typing import Any
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from catalog.models import Author, Book, Language


class SearchListTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Never touch a real cluster from tests. This must be patched before setUpTestData
        # runs, because creating a Book or Author fires signals that call index_document().
        for name in ('index_document', 'delete_document'):
            patcher = mock.patch(f'catalog.search.{name}')
            patcher.start()
            cls.addClassCleanup(patcher.stop)
        super().setUpClass()

    @classmethod
    def setUpTestData(cls) -> None:
        cls.asimov = Author.objects.create(first_name='Isaac', last_name='Asimov')
        cls.leguin = Author.objects.create(first_name='Ursula', last_name='Le Guin')
        language = Language.objects.create(name='English')
        cls.foundation = Book.objects.create(
            title='Foundation', author=cls.asimov, summary='Empire', isbn='1111111111111', language=language)
        cls.robot = Book.objects.create(
            title='I, Robot', author=cls.asimov, summary='Robots', isbn='2222222222222', language=language)

    def get(self, name: str, ids: list[int] | None = None, **params: str) -> tuple[Any, mock.MagicMock]:
        """GET a list page; `ids` is what the mocked OpenSearch returns for a query."""
        with mock.patch('catalog.views.search.search_ids', return_value=ids or []) as search_ids:
            response = self.client.get(reverse(name), params)
        return response, search_ids

    def test_no_query_lists_everything_without_calling_search(self) -> None:
        response, search_ids = self.get('books')
        search_ids.assert_not_called()
        self.assertEqual(len(response.context['book_list']), 2)

    def test_book_query_keeps_opensearch_relevance_order(self) -> None:
        response, search_ids = self.get('books', ids=[self.robot.pk, self.foundation.pk], q='robot')
        search_ids.assert_called_once_with(Book, 'robot')
        self.assertEqual(list(response.context['book_list']), [self.robot, self.foundation])

    def test_author_query_searches_the_author_index(self) -> None:
        response, search_ids = self.get('authors', ids=[self.leguin.pk], q='ursula')
        search_ids.assert_called_once_with(Author, 'ursula')
        self.assertEqual(list(response.context['author_list']), [self.leguin])

    def test_query_with_no_hits_shows_empty_message(self) -> None:
        response, _ = self.get('books', q='zzz')
        self.assertContains(response, 'No books match your search.')

    def test_pagination_links_keep_the_query(self) -> None:
        authors = [Author(first_name=f'A{i}', last_name='Same') for i in range(11)]
        ids = [a.pk for a in Author.objects.bulk_create(authors)]
        response, _ = self.get('authors', ids=ids, q='same')
        self.assertContains(response, '?q=same&amp;page=2')
