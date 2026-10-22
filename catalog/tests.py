from typing import Any
from unittest import mock

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

from catalog import search
from catalog.models import Author, Book, Language


class SearchListTests(TestCase):
    def setUp(self) -> None:
        self.down = OpenSearchConnectionError('N/A', 'cluster unreachable', OSError('connection refused'))
        return super().setUp()

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


class ProbeTests(TestCase):
    def functionalz(self, opensearch_up: bool = True, db_error: Exception | None = None) -> Any:
        with (
            mock.patch('catalog.search.is_up', return_value=opensearch_up),
            mock.patch('catalog.middleware.connection.cursor', side_effect=db_error),
        ):
            return self.client.get('/functionalz/')

    def test_healthz_is_200_without_touching_database_or_opensearch(self) -> None:
        with (
            mock.patch('catalog.search.is_up') as is_up,
            mock.patch('catalog.middleware.connection.cursor', side_effect=AssertionError('db touched')),
        ):
            response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        is_up.assert_not_called()

    def test_functionalz_is_200_when_database_answers(self) -> None:
        self.assertEqual(self.functionalz().status_code, 200)

    def test_functionalz_is_503_when_database_fails(self) -> None:
        self.assertEqual(self.functionalz(db_error=OperationalError('db down')).status_code, 503)

    def test_functionalz_reports_opensearch_up(self) -> None:
        self.assertEqual(self.functionalz(opensearch_up=True).json()['opensearch'], 'up')

    def test_functionalz_reports_opensearch_down_without_changing_status(self) -> None:
        response = self.functionalz(opensearch_up=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['opensearch'], 'down')

    def test_probes_ignore_allowed_hosts(self) -> None:
        for path in ('/healthz/', '/functionalz/'):
            with self.subTest(path=path), mock.patch('catalog.search.is_up', return_value=True):
                response = self.client.get(path, headers={'host': '10.1.2.3'})
                self.assertEqual(response.status_code, 200)

    def test_is_up_is_false_when_cluster_unreachable(self) -> None:
        client = mock.Mock()
        client.ping.side_effect = OpenSearchConnectionError('N/A', 'unreachable', OSError('refused'))
        with mock.patch('catalog.search.get_client', return_value=client):
            self.assertFalse(search.is_up())
