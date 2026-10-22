"""Kubernetes probe endpoints, answered before host validation so pod-IP probes work."""
import logging
from collections.abc import Callable

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse

from . import search

logger = logging.getLogger(__name__)


class ProbeMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path in ('/healthz', '/healthz/'):
            return HttpResponse('ok', content_type='text/plain')
        if request.path in ('/functionalz', '/functionalz/'):
            return self.functionalz()
        return self.get_response(request)

    @staticmethod
    def functionalz() -> JsonResponse:
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            database = 'up'
        except Exception:  # any probe failure means 'down', never an unhandled 500
            logger.warning('Database probe failed', exc_info=True)
            database = 'down'
        body = {'database': database, 'opensearch': 'up' if search.is_up() else 'down'}
        return JsonResponse(body, status=200 if database == 'up' else 503)
