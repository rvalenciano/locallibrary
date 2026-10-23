from django.db.models import CharField, DateField, Field, Model
from django.test import TestCase

from catalog.models import Author


def get_model_field[F: Field](model: type[Model], name: str, field_type: type[F]) -> F:
    # get_field() is typed as Field | ForeignObjectRel; narrow it to the expected field class
    # so the type checker allows verbose_name and max_length.
    field = model._meta.get_field(name)
    assert isinstance(field, field_type)
    return field


class AuthorModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Set up non-modified objects used by all test methods
        Author.objects.create(first_name='Big', last_name='Bob')

    def test_first_name_label(self):
        field_label = get_model_field(Author, 'first_name', CharField).verbose_name
        self.assertEqual(field_label, 'first name')

    def test_date_of_death_label(self):
        field_label = get_model_field(Author, 'date_of_death', DateField).verbose_name
        self.assertEqual(field_label, 'died')

    def test_first_name_max_length(self):
        max_length = get_model_field(Author, 'first_name', CharField).max_length
        self.assertEqual(max_length, 100)

    def test_object_name_is_last_name_comma_first_name(self):
        author = Author.objects.get(id=1)
        expected_object_name = f'{author.last_name}, {author.first_name}'
        self.assertEqual(str(author), expected_object_name)

    def test_get_absolute_url(self):
        author = Author.objects.get(id=1)
        # This will also fail if the URLConf is not defined.
        self.assertEqual(author.get_absolute_url(), '/catalog/authors/1')
