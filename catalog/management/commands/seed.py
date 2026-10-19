from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog import search
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
    ("J. R. R.", "Tolkien", date(1892, 1, 3), date(1973, 9, 2)),
    ("Frank", "Herbert", date(1920, 10, 8), date(1986, 2, 11)),
    ("Philip K.", "Dick", date(1928, 12, 16), date(1982, 3, 2)),
    ("Ray", "Bradbury", date(1920, 8, 22), date(2012, 6, 5)),
    ("Terry", "Pratchett", date(1948, 4, 28), date(2015, 3, 12)),
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
    ("Foundation and Empire", "Asimov", "9785100000013", "English", ["Science Fiction"],
     "A general of the Empire's last great fleet and a mysterious mutant, the Mule, threaten the Foundation."),
    ("Second Foundation", "Asimov", "9785100000020", "English", ["Science Fiction"],
     "The Foundation hunts for the hidden group of mentalists said to guard the future of humanity."),
    ("The Caves of Steel", "Asimov", "9785100000037", "English", ["Science Fiction", "Mystery"],
     "A New York detective teams up with a humanoid robot to solve a murder in a crowded domed city."),
    ("The Naked Sun", "Asimov", "9785100000044", "English", ["Science Fiction", "Mystery"],
     "The same detective-and-robot pair investigates a killing on a planet where people never meet in person."),
    ("The End of Eternity", "Asimov", "9785100000051", "English", ["Science Fiction"],
     "A technician in an order that edits history falls in love and risks undoing the whole of time."),
    ("The Gods Themselves", "Asimov", "9785100000068", "English", ["Science Fiction"],
     "Scientists discover a source of limitless energy that comes at a terrifying cost across two universes."),
    ("The Dispossessed", "Le Guin", "9785100000075", "English", ["Science Fiction", "Classic"],
     "A physicist leaves his anarchist moon for its wealthy twin planet and questions both societies."),
    ("The Lathe of Heaven", "Le Guin", "9785100000082", "English", ["Science Fiction"],
     "A man whose dreams change reality is treated by a doctor who wants to use that power."),
    ("The Tombs of Atuan", "Le Guin", "9785100000099", "English", ["Fantasy"],
     "A young priestess guarding ancient tombs meets a wizard who may free her."),
    ("The Farthest Shore", "Le Guin", "9785100000105", "English", ["Fantasy"],
     "Ged and a young prince travel to the edge of the world to find why magic is fading."),
    ("Tehanu", "Le Guin", "9785100000112", "English", ["Fantasy"],
     "Tenar adopts a burned child and faces danger as the old wizard Ged returns without his power."),
    ("The Obelisk Gate", "Jemisin", "9785100000129", "English", ["Fantasy", "Science Fiction"],
     "Essun searches for her daughter while learning to control the forces that shake her world."),
    ("The Stone Sky", "Jemisin", "9785100000136", "English", ["Fantasy", "Science Fiction"],
     "The truth behind the endless Seasons is revealed as mother and daughter face a final choice."),
    ("The City We Became", "Jemisin", "9785100000143", "English", ["Fantasy", "Science Fiction"],
     "The avatars of New York's boroughs awaken to defend their city from an ancient enemy."),
    ("The Hundred Thousand Kingdoms", "Jemisin", "9785100000150", "English", ["Fantasy"],
     "A young woman from a remote land inherits a place in a deadly contest among the ruling family."),
    ("The Hobbit", "Tolkien", "9785100000167", "English", ["Fantasy", "Classic"],
     "A homebody hobbit joins a company of dwarves to win back their treasure from a dragon."),
    ("The Fellowship of the Ring", "Tolkien", "9785100000174", "English", ["Fantasy", "Classic"],
     "Frodo leaves the Shire with eight companions to carry the One Ring toward Mordor."),
    ("The Two Towers", "Tolkien", "9785100000181", "English", ["Fantasy", "Classic"],
     "The Fellowship is broken as Frodo presses on to Mordor and his friends fight at Helm's Deep."),
    ("The Return of the King", "Tolkien", "9785100000198", "English", ["Fantasy", "Classic"],
     "Armies gather at Gondor while Frodo and Sam climb Mount Doom to destroy the Ring."),
    ("The Silmarillion", "Tolkien", "9785100000204", "English", ["Fantasy"],
     "The creation of Middle-earth and the long wars over the Silmarils in its First Age."),
    ("Dune", "Herbert", "9785100000211", "English", ["Science Fiction", "Classic"],
     "Paul Atreides takes his family to the desert planet Arrakis, the only source of the spice."),
    ("Dune Messiah", "Herbert", "9785100000228", "English", ["Science Fiction"],
     "Paul rules the galaxy as emperor while a conspiracy gathers against him."),
    ("Children of Dune", "Herbert", "9785100000235", "English", ["Science Fiction"],
     "Paul's twin children inherit a ruined empire and the burden of his visions."),
    ("God Emperor of Dune", "Herbert", "9785100000242", "English", ["Science Fiction"],
     "Thousands of years later, Leto II rules as a tyrant to steer humanity toward survival."),
    ("Do Androids Dream of Electric Sheep?", "Dick", "9785100000259", "English", ["Science Fiction", "Classic"],
     "A bounty hunter retires rogue androids in a ruined future and begins to doubt the line between human and machine."),
    ("The Man in the High Castle", "Dick", "9785100000266", "English", ["Science Fiction"],
     "In an America ruled by the Axis powers, a banned novel imagines that the Allies won."),
    ("Ubik", "Dick", "9785100000273", "English", ["Science Fiction"],
     "After an accident, a team of psychic agents finds reality fading into the past."),
    ("A Scanner Darkly", "Dick", "9785100000280", "English", ["Science Fiction"],
     "An undercover narcotics agent loses his identity while hunting a drug he is addicted to."),
    ("VALIS", "Dick", "9785100000297", "English", ["Science Fiction"],
     "A man haunted by a vision of a divine intelligence searches for its meaning."),
    ("Fahrenheit 451", "Bradbury", "9785100000303", "English", ["Science Fiction", "Classic"],
     "A fireman who burns books begins to question his society's ban on reading."),
    ("The Martian Chronicles", "Bradbury", "9785100000310", "English", ["Science Fiction", "Classic"],
     "Linked stories follow the human colonization of Mars and its native people."),
    ("Something Wicked This Way Comes", "Bradbury", "9785100000327", "English", ["Fantasy", "Classic"],
     "Two boys uncover the dark secret of a carnival that arrives in town one October night."),
    ("The Illustrated Man", "Bradbury", "9785100000334", "English", ["Science Fiction"],
     "A tattooed wanderer's skin comes alive with stories of the future."),
    ("The Colour of Magic", "Pratchett", "9785100000341", "English", ["Fantasy"],
     "A hapless wizard and the Disc's first tourist set off on a chaotic adventure."),
    ("Mort", "Pratchett", "9785100000358", "English", ["Fantasy"],
     "Death takes on an apprentice, who soon starts to meddle with fate."),
    ("Guards! Guards!", "Pratchett", "9785100000365", "English", ["Fantasy"],
     "The Ankh-Morpork City Watch faces a dragon summoned to put a false king on the throne."),
    ("Small Gods", "Pratchett", "9785100000372", "English", ["Fantasy"],
     "A novice in a powerful church finds that his god is a tortoise with almost no followers."),
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
        # Signals swallow indexing errors, so check up front rather than seed rows that never get indexed.
        if not search.get_client().ping():
            raise CommandError(
                "OpenSearch is unreachable, so seeded books would not be searchable. "
                "Start it with `docker compose up -d`, or run `python manage.py search_index` after seeding."
            )

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
