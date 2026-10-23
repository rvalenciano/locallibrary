import logging
from typing import Any

from django.db.models import Case, IntegerField, QuerySet, When
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from opensearchpy.exceptions import OpenSearchException

# Create your views here.
from . import search
from .models import Author, Book, BookInstance

logger = logging.getLogger(__name__)

def index(request: HttpRequest) -> HttpResponse:
    """View function for home page of site."""

    # Generate counts of some of the main objects
    num_books = Book.objects.all().count()
    num_instances = BookInstance.objects.all().count()

    # Available books (status = 'a')
    num_instances_available = BookInstance.objects.filter(status__exact='a').count()

    # The 'all()' is implied by default.
    num_authors = Author.objects.count()

    context = {
        'num_books': num_books,
        'num_instances': num_instances,
        'num_instances_available': num_instances_available,
        'num_authors': num_authors,
    }

    # Render the HTML template index.html with the data in the context variable
    return render(request, 'index.html', context=context)



from django.views import generic


class SearchListView(generic.ListView):
    """List view that, given ?q=, shows the OpenSearch matches in relevance order."""
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Any]:
        queryset = super().get_queryset()
        self.query = self.request.GET.get('q', '').strip()
        self.search_degraded = False
        if not self.query:
            return queryset

        assert self.model is not None, 'SearchListView subclasses must set model'
        try:
            ids = search.search_ids(self.model, self.query)
        except OpenSearchException:
            # Covers ConnectionError, timeouts, 5xx and a missing index: search can't answer, so use the database.
            logger.warning('OpenSearch unavailable; searching the database for %r', self.query, exc_info=True)
            self.search_degraded = True
            return search.fallback_queryset(self.model, queryset, self.query)
        # Keep OpenSearch's relevance order: ORDER BY CASE WHEN pk = <id> THEN <rank> ...
        relevance = Case(*[When(pk=pk, then=rank) for rank, pk in enumerate(ids)], output_field=IntegerField())
        return queryset.filter(pk__in=ids).order_by(relevance)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['q'] = self.query
        context['search_degraded'] = self.search_degraded
        return context



class BookListView(SearchListView):
    model = Book
    queryset = Book.objects.select_related('author')
    ordering = ['title']


class AuthorListView(SearchListView):
    model = Author


class BookDetailView(generic.DetailView):
    model = Book
    paginate_by = 10


class AuthorDetailView(generic.DetailView):
    model = Author
    paginate_by = 10


from django.contrib.auth.mixins import LoginRequiredMixin


class LoanedBooksByUserListView(LoginRequiredMixin,generic.ListView):
    """Generic class-based view listing books on loan to current user."""
    model = BookInstance
    template_name = 'catalog/bookinstance_list_borrowed_user.html'
    paginate_by = 10

    def get_queryset(self):
        return (
            BookInstance.objects.filter(borrower=self.request.user)
            .filter(status__exact='o')
            .order_by('due_back')
        )


from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class LoanedBooksAllListView(PermissionRequiredMixin, generic.ListView):
    """Lists every book on loan. Librarians only."""
    model = BookInstance
    permission_required = 'catalog.can_mark_returned'
    template_name = 'catalog/bookinstance_list_borrowed_all.html'
    paginate_by = 10

    def get_queryset(self):
        return (
            BookInstance.objects.filter(status__exact='o')
            .select_related('book', 'borrower')
            .order_by('due_back')
        )
