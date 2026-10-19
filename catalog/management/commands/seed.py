from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Author, Book, BookInstance, Genre, Language

GENRES = ["Science Fiction", "Fantasy", "Mystery", "Classic", "Poetry"]
LANGUAGES = ["English", "Spanish", "French"]

AUTHORS = [
    # (first_name, last_name, date_of_birth, date_of_death)
    ("Isaac", "Asimov", date(1920, 1, 2), date(1992, 4, 6)),
    ("Ursula", "Le Guin", date(1929, 10, 21), date(2018, 1, 22)),
    ("Agatha", "Christie", date(1890, 9, 15), date(1976, 1, 12)),
    ("Gabriel", "García Márquez", date(1927, 3, 6), date(2014, 4, 17)),
    ("N. K.", "Jemisin", date(1972, 9, 19), None),
]

BOOKS = [
    # (title, author last_name, isbn, language, genres, summary)
    ("Foundation", "Asimov", "9780553293357", "English", ["Science Fiction"],
     "A mathematician predicts the fall of a galactic empire and plans to shorten the dark age that follows."),
    ("I, Robot", "Asimov", "9780553382563", "English", ["Science Fiction"],
     "Linked stories exploring the Three Laws of Robotics and their unintended consequences."),
    ("A Wizard of Earthsea", "Le Guin", "9780547773742", "English", ["Fantasy"],
     "A young wizard unleashes a shadow and must hunt it across the archipelago."),
    ("The Left Hand of Darkness", "Le Guin", "9780441478125", "English", ["Science Fiction", "Classic"],
     "An envoy visits a world whose people have no fixed gender."),
    ("Murder on the Orient Express", "Christie", "9780062693662", "English", ["Mystery", "Classic"],
     "Hercule Poirot investigates a murder aboard a snowbound train."),
    ("Cien años de soledad", "García Márquez", "9780307474728", "Spanish", ["Classic", "Fantasy"],
     "Seven generations of the Buendía family in the town of Macondo."),
    ("The Fifth Season", "Jemisin", "9780316229296", "English", ["Fantasy", "Science Fiction"],
     "On a continent that suffers apocalyptic seasons, a mother searches for her daughter."),
]


class Command(BaseCommand):
    help = "Seed the database with sample catalog data (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all catalog data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.reset()

        genres = {n: Genre.objects.get_or_create(name=n)[0] for n in GENRES}
        languages = {n: Language.objects.get_or_create(name=n)[0] for n in LANGUAGES}

        authors = {}
        for first, last, born, died in AUTHORS:
            authors[last], _ = Author.objects.get_or_create(
                first_name=first,
                last_name=last,
                defaults={"date_of_birth": born, "date_of_death": died},
            )

        today = date.today()
        statuses = ["a", "o", "m", "r"]
        copies_created = 0
        for title, author, isbn, language, genre_names, summary in BOOKS:
            book, _ = Book.objects.get_or_create(
                title=title,
                author=authors[author],
                defaults={
                    "isbn": isbn,
                    "summary": summary,
                    "language": languages[language],
                },
            )
            book.genre.add(*(genres[n] for n in genre_names))  # add() ignores existing links

            for copy in range(1, book.pk % 5 + 2):  # 1 to 5 copies
                status = statuses[(book.pk + copy) % len(statuses)]
                _, created = BookInstance.objects.get_or_create(
                    book=book,
                    imprint=f"First edition, copy {copy}",
                    defaults={
                        "status": status,
                        "due_back": today + timedelta(days=7 * copy) if status == "o" else None,
                    },
                )
                copies_created += created

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Genre.objects.count()} genres, {Language.objects.count()} languages, "
            f"{Author.objects.count()} authors, {Book.objects.count()} books, "
            f"{BookInstance.objects.count()} copies ({copies_created} new)."
        ))

    def reset(self):
        # Children first: Book/BookInstance foreign keys use on_delete=RESTRICT.
        BookInstance.objects.all().delete()
        Book.objects.all().delete()
        Author.objects.all().delete()
        Genre.objects.all().delete()
        Language.objects.all().delete()
        self.stdout.write("Existing catalog data deleted.")
