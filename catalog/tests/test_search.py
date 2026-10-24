from typing import Any
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

from catalog import index_sync
from catalog.models import Author, Book, Language

from .fakes import FakeIndex


class SearchListTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Never touch a real cluster from tests. This must be in place before setUpTestData
        # runs, because creating a Book or Author writes to the index.
        cls.enterClassContext(index_sync.use_index(FakeIndex()))
        super().setUpClass()

    def setUp(self) -> None:
        self.down = OpenSearchConnectionError('N/A', 'cluster unreachable', OSError('connection refused'))
        return super().setUp()

    @classmethod
    def setUpTestData(cls) -> None:
        cls.asimov = Author.objects.create(first_name='Isaac', last_name='Asimov')
        cls.leguin = Author.objects.create(first_name='Ursula', last_name='Le Guin')
        language = Language.objects.create(name='English')
        cls.foundation = Book.objects.create(
            title='Foundation', author=cls.asimov, summary='Empire', isbn='1111111111111', language=language)
        cls.robot = Book.objects.create(
            title='I, Robot', author=cls.asimov, summary='Robots', isbn='2222222222222', language=language)

    def get(self, name: str, ids: list[int] | None = None, side_effect: Exception | None = None, **params: str) -> tuple[Any, mock.MagicMock]:
        """GET a list page; `ids` is what the mocked OpenSearch returns, `side_effect` makes it fail."""
        with mock.patch('catalog.views.search.search_ids', return_value=ids or [], side_effect=side_effect) as search_ids:
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

    def test_book_search_falls_back_to_database_when_opensearch_is_down(self) -> None:
        with self.assertLogs('catalog.views', level='WARNING') as logs:
            response, _ = self.get('books', side_effect=self.down, q='foundation')
        self.assertIn('OpenSearch unavailable', logs.output[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['book_list']), [self.foundation])
        self.assertContains(response, 'Search is temporarily unavailable')

    def test_fallback_requires_every_term_to_match(self) -> None:
        with self.assertLogs('catalog.views', level='WARNING'):
            response, _ = self.get('books', side_effect=self.down, q='isaac asimov')
            self.assertEqual(list(response.context['book_list']), [self.foundation, self.robot])
            response, _ = self.get('books', side_effect=self.down, q='isaac leguin')
            self.assertEqual(list(response.context['book_list']), [])

    def test_author_search_falls_back_to_database_when_opensearch_is_down(self) -> None:
        with self.assertLogs('catalog.views', level='WARNING'):
            response, _ = self.get('authors', side_effect=self.down, q='ursula')
        self.assertEqual(list(response.context['author_list']), [self.leguin])
        self.assertContains(response, 'Search is temporarily unavailable')

    def test_no_warning_when_opensearch_answers(self) -> None:
        response, _ = self.get('books', ids=[self.robot.pk], q='robot')
        self.assertNotContains(response, 'Search is temporarily unavailable')

    def test_empty_query_never_falls_back(self) -> None:
        with self.assertNoLogs('catalog.views', level='WARNING'):
            response, search_ids = self.get('books', side_effect=self.down)
        search_ids.assert_not_called()
        self.assertNotContains(response, 'Search is temporarily unavailable')
