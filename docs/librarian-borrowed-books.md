# How to: a librarian-only page listing all borrowed books

Follows the MDN tutorial
[Django Authentication — permissions](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Server-side/Django/Authentication#permissions),
building on the existing "My Borrowed" page (`LoanedBooksByUserListView`).

Goal: `/catalog/borrowed/` lists every `BookInstance` on loan, shows who has it,
and is only reachable by users who hold the librarian permission.

## How the pieces fit

| Concept | What it is here |
| --- | --- |
| Permission | `catalog.can_mark_returned`, declared on `BookInstance.Meta` |
| Group | `Librarians`, holds that permission |
| User | any user added to `Librarians` (the seed adds `libby`) |
| Guard | `PermissionRequiredMixin` on the view |

The tutorial calls the permission `can_mark_returned` because later steps
(renewing books) reuse it. Keep that name for continuity.

> You said "role". Django has no roles: a role is a **group** carrying
> **permissions**. So steps 1 and 2 are really "define a permission" and
> "define a group that holds it".

---

## Step 1 — Define the permission (model + migration)

Permissions are declared on the model, not in the seed. The seed can only
*assign* a permission that already exists.

`catalog/models.py`, in `BookInstance.Meta`:

```python
class Meta:
    ordering = ['due_back']
    permissions = (("can_mark_returned", "Set book as returned"),)
```

Then create and apply the migration:

```bash
python manage.py makemigrations catalog
python manage.py migrate
```

Django creates the `Permission` row for it in the `post_migrate` step.

## Step 2 — Create the group and assign the permission (seed command)

Yes, do it in `seed`: it keeps dev data reproducible. Permissions exist only
after `migrate`, so the seed must run after it (it already has to).

`catalog/management/commands/seed.py`:

```python
from django.contrib.auth.models import Group, Permission

LIBRARIAN_GROUP = "Librarians"
LIBRARIAN_USERNAME = "libby"
```

Inside `handle`, next to where the borrower users are created:

```python
permission = Permission.objects.get(
    content_type__app_label="catalog",
    codename="can_mark_returned",
)
librarians, _ = Group.objects.get_or_create(name=LIBRARIAN_GROUP)
librarians.permissions.add(permission)  # add() is idempotent

librarian, created = user_model.objects.get_or_create(
    username=LIBRARIAN_USERNAME,
    defaults={"first_name": "Libby", "last_name": "Librarian", "email": "libby@example.com"},
)
if created:
    librarian.set_password(USER_PASSWORD)
    librarian.save()
librarian.groups.add(librarians)
```

Keep `libby` **out** of the `USERS` borrower list so she isn't handed loans.

In `reset()`, delete her too, otherwise `--reset` leaves her behind:

```python
get_user_model().objects.filter(
    username__in=[u for u, _, _ in USERS] + [LIBRARIAN_USERNAME]
).delete()
```

Optionally add the group itself (`Group.objects.filter(name=LIBRARIAN_GROUP).delete()`).
Also add `libby` to the "Seed users" line printed at the end.

Verify without the UI:

```bash
python manage.py seed
python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='libby')
print(u.has_perm('catalog.can_mark_returned'))
"
```

Expected: `True`. (A fresh `User` object matters: Django caches permissions on
the instance, so a user fetched before the group change won't see it.)

## Step 3 — The permission-protected view

`catalog/views.py`:

```python
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class LoanedBooksAllListView(PermissionRequiredMixin, generic.ListView):
    """Lists every book on loan. Librarians only."""
    model = BookInstance
    permission_required = 'catalog.can_mark_returned'
    template_name = 'catalog/bookinstance_list_borrowed_all.html'
    paginate_by = 10
```

Behaviour of `PermissionRequiredMixin` to be aware of:

- Anonymous user → redirected to the login page (good).
- Logged in **without** the permission → **403 Forbidden**, not a redirect.
  This is the right outcome; optionally add a `templates/403.html`.
- Superusers always pass `has_perm`, so test with `libby` and a normal user
  such as `alice`, not just your admin account.

## Step 4 — Override the queryset

Same view, add `get_queryset`:

```python
def get_queryset(self):
    return (
        BookInstance.objects.filter(status__exact='o')
        .select_related('book', 'borrower')
        .order_by('due_back')
    )
```

- `status='o'` is what "borrowed" means everywhere else in this project (it is
  also what the per-user view filters on).
- `select_related` avoids one query per row for the book title and borrower name.
- Unlike the per-user view, there is no `borrower=request.user` filter.

## Step 5 — URL

`catalog/urls.py`, next to `my-borrowed`:

```python
urlpatterns += [
    path('borrowed/', views.LoanedBooksAllListView.as_view(), name='all-borrowed'),
]
```

## Step 6 — Template

`catalog/templates/catalog/bookinstance_list_borrowed_all.html`:

```django
{% extends "base_generic.html" %}

{% block content %}
  <h1>All borrowed books</h1>

  {% if bookinstance_list %}
  <ul>
    {% for bookinst in bookinstance_list %}
    <li class="{% if bookinst.is_overdue %}text-danger{% endif %}">
      <a href="{% url 'book-detail' bookinst.book.pk %}">{{ bookinst.book.title }}</a>
      ({{ bookinst.due_back }}) — {{ bookinst.borrower.get_full_name|default:bookinst.borrower.username }}
    </li>
    {% endfor %}
  </ul>
  {% else %}
    <p>There are no books borrowed.</p>
  {% endif %}
{% endblock %}
```

`borrower` is nullable (`SET_NULL`), so a copy marked `o` with no borrower
would render an empty name; the `default` filter doesn't cover that case. If
you want to be defensive, use
`{{ bookinst.borrower|default:"—" }}` and accept the username display, or
filter `borrower__isnull=False` in the queryset.

Pagination: `paginate_by = 10` only works if the template renders page links.
Copy the pagination block from `book_list.html` if you want it.

## Step 7 — Show the link only to librarians

`catalog/templates/base_generic.html`, inside the `user.is_authenticated`
branch. Django exposes the logged-in user's permissions as `perms`:

```django
{% if perms.catalog.can_mark_returned %}
  <li><a href="{% url 'all-borrowed' %}">All borrowed</a></li>
{% endif %}
```

Hiding the link is only cosmetic; the view mixin from step 3 is the real guard.

## Step 8 — Tests (the part that's easy to forget)

Cover the three access cases and the queryset. In `catalog/tests/`:

```python
from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse

from catalog.models import Book, BookInstance


class AllBorrowedViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('all-borrowed')
        cls.borrower = User.objects.create_user('alice', password='pw')
        cls.reader = User.objects.create_user('reader', password='pw')
        cls.librarian = User.objects.create_user('libby', password='pw')
        group = Group.objects.create(name='Librarians')
        group.permissions.add(Permission.objects.get(codename='can_mark_returned'))
        cls.librarian.groups.add(group)

        book = Book.objects.create(title='T', summary='s', isbn='1234567890123')
        BookInstance.objects.create(book=book, imprint='x', status='o', borrower=cls.borrower)
        BookInstance.objects.create(book=book, imprint='y', status='a')

    def test_anonymous_redirected_to_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_user_without_permission_gets_403(self):
        self.client.login(username='reader', password='pw')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_librarian_sees_only_borrowed_copies_with_borrower(self):
        self.client.login(username='libby', password='pw')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['bookinstance_list']), 1)
        self.assertContains(response, 'alice')
```

Adjust the `Book.objects.create` fields to whatever the model requires.

## Step 9 — Try it by hand

```bash
python manage.py seed
python manage.py runserver
```

| Log in as | Visit `/catalog/borrowed/` | Sidebar link |
| --- | --- | --- |
| nobody | redirect to login | no |
| `alice` | 403 | no |
| `libby` | list of all loans with borrower names | yes |

Password for all seed users is in `USER_PASSWORD` in `seed.py`.

## Things that are easy to miss

- **Migration for the permission** (step 1). Without it the seed's
  `Permission.objects.get` raises `DoesNotExist`.
- **Seed ordering**: run `migrate` before `seed`, in dev, CI and the Docker image.
- **Seed idempotency**: use `get_or_create` / `.add()` so reruns don't error or duplicate.
- **`--reset` cleanup** of the librarian user (and optionally the group).
- **403 vs login redirect**: the mixin redirects anonymous users but returns 403
  to logged-in users without the permission.
- **Superuser bypass** when manually testing.
- **Production**: the group/permission wiring is data, so on a real database
  create the group once via the admin (Authentication and Authorization →
  Groups) or a data migration; don't rely on the dev seed there.
- **Docs**: if "librarian" becomes a domain term, add it to `GLOSSARY.md`.
