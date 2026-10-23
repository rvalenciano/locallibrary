import os
from argparse import ArgumentParser
from datetime import date, timedelta
from typing import Any

from django.contrib.auth import get_user_model
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
    ("Jane", "Austen", date(1775, 12, 16), date(1817, 7, 18)),
    ("Charles", "Dickens", date(1812, 2, 7), date(1870, 6, 9)),
    ("Arthur", "Conan Doyle", date(1859, 5, 22), date(1930, 7, 7)),
    ("Edgar Allan", "Poe", date(1809, 1, 19), date(1849, 10, 7)),
    ("Walt", "Whitman", date(1819, 5, 31), date(1892, 3, 26)),
    ("Emily", "Dickinson", date(1830, 12, 10), date(1886, 5, 15)),
    ("Jorge Luis", "Borges", date(1899, 8, 24), date(1986, 6, 14)),
    ("Miguel de", "Cervantes", date(1547, 9, 29), date(1616, 4, 22)),
    ("Isabel", "Allende", date(1942, 8, 2), None),
]

USERS = [
    # (username, first_name, last_name)
    ("alice", "Alice", "Anderson"),
    ("bob", "Bob", "Baker"),
    ("carol", "Carol", "Chen"),
    ("dave", "Dave", "Diaz"),
    ("erin", "Erin", "Evans"),
]
SEED_PASSWORD_ENV = "SEED_USER_PASSWORD"

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
    ("Pride and Prejudice", "Austen", "9785200000012", "English", ["Classic"],
     "Elizabeth Bennet and the proud Mr. Darcy overcome first impressions and class prejudice."),
    ("Sense and Sensibility", "Austen", "9785200000029", "English", ["Classic"],
     "Two sisters, one sensible and one passionate, navigate love and money after their father's death."),
    ("Emma", "Austen", "9785200000036", "English", ["Classic"],
     "A confident young matchmaker meddles in her friends' lives and learns about her own heart."),
    ("Persuasion", "Austen", "9785200000043", "English", ["Classic"],
     "Anne Elliot meets again the naval officer she was persuaded to refuse eight years earlier."),
    ("Northanger Abbey", "Austen", "9785200000050", "English", ["Classic"],
     "A young woman with a taste for gothic novels visits an abbey and lets her imagination run away."),
    ("Mansfield Park", "Austen", "9785200000067", "English", ["Classic"],
     "Quiet Fanny Price is raised among wealthy relatives and holds to her principles."),
    ("Oliver Twist", "Dickens", "9785200000074", "English", ["Classic"],
     "An orphan escapes a workhouse and falls in with a gang of London pickpockets."),
    ("Great Expectations", "Dickens", "9785200000081", "English", ["Classic"],
     "Pip, a poor orphan, is given a mysterious fortune and a chance to become a gentleman."),
    ("A Tale of Two Cities", "Dickens", "9785200000098", "English", ["Classic"],
     "Lives in London and Paris collide during the French Revolution."),
    ("David Copperfield", "Dickens", "9785200000104", "English", ["Classic"],
     "A boy grows up through hardship and friendship toward a career as a writer."),
    ("Bleak House", "Dickens", "9785200000111", "English", ["Classic"],
     "A never-ending lawsuit draws together a wide circle of Londoners and their secrets."),
    ("Hard Times", "Dickens", "9785200000128", "English", ["Classic"],
     "A schoolmaster devoted to facts sees his children suffer in an industrial town."),
    ("A Christmas Carol", "Dickens", "9785200000135", "English", ["Classic", "Fantasy"],
     "The miser Ebenezer Scrooge is visited by three ghosts on Christmas Eve."),
    ("Little Dorrit", "Dickens", "9785200000142", "English", ["Classic"],
     "A girl born in a debtors' prison becomes entangled in her family's fortunes."),
    ("Nicholas Nickleby", "Dickens", "9785200000159", "English", ["Classic"],
     "A young man must support his family after his father's death and confronts cruel schoolmasters."),
    ("Our Mutual Friend", "Dickens", "9785200000166", "English", ["Classic", "Mystery"],
     "A fortune, a disputed will and a body in the Thames bind together London's rich and poor."),
    ("A Study in Scarlet", "Conan Doyle", "9785200000173", "English", ["Mystery", "Classic"],
     "Sherlock Holmes and Dr. Watson meet and investigate a murder with a single word written in blood."),
    ("The Sign of the Four", "Conan Doyle", "9785200000180", "English", ["Mystery", "Classic"],
     "Holmes follows a mysterious treasure and a set of cryptic clues for Mary Morstan."),
    ("The Hound of the Baskervilles", "Conan Doyle", "9785200000197", "English", ["Mystery", "Classic"],
     "Holmes investigates a spectral hound said to haunt a family on the Devon moors."),
    ("The Adventures of Sherlock Holmes", "Conan Doyle", "9785200000203", "English", ["Mystery", "Classic"],
     "Twelve short cases, including Holmes's encounter with Irene Adler."),
    ("The Memoirs of Sherlock Holmes", "Conan Doyle", "9785200000210", "English", ["Mystery", "Classic"],
     "More short cases, ending with Holmes's struggle with Professor Moriarty."),
    ("The Valley of Fear", "Conan Doyle", "9785200000227", "English", ["Mystery"],
     "A coded warning leads Holmes to a murder and a secret society in the Pennsylvania coal fields."),
    ("The Lost World", "Conan Doyle", "9785200000234", "English", ["Science Fiction", "Classic"],
     "Professor Challenger leads an expedition to a South American plateau where dinosaurs survive."),
    ("Tales of Mystery and Imagination", "Poe", "9785200000241", "English", ["Mystery", "Classic"],
     "Classic horror and detective stories, including The Tell-Tale Heart and The Fall of the House of Usher."),
    ("The Raven and Other Poems", "Poe", "9785200000258", "English", ["Poetry", "Classic"],
     "The haunting title poem and others on loss and death."),
    ("The Narrative of Arthur Gordon Pym of Nantucket", "Poe", "9785200000265", "English", ["Classic"],
     "A stowaway's sea voyage turns into mutiny, shipwreck and a journey toward the South Pole."),
    ("Tales of the Grotesque and Arabesque", "Poe", "9785200000272", "English", ["Mystery", "Classic"],
     "Early stories of horror, satire and dark humor."),
    ("Leaves of Grass", "Whitman", "9785200000289", "English", ["Poetry", "Classic"],
     "A sweeping collection celebrating the self, democracy and the body."),
    ("Drum-Taps", "Whitman", "9785200000296", "English", ["Poetry"],
     "Poems of the American Civil War, from marching armies to field hospitals."),
    ("November Boughs", "Whitman", "9785200000302", "English", ["Poetry"],
     "Late poems and prose reflections gathered by the aging poet."),
    ("Poems: Series One", "Dickinson", "9785200000319", "English", ["Poetry", "Classic"],
     "The first collection of Emily Dickinson's short poems on nature, death and the soul."),
    ("Poems: Series Two", "Dickinson", "9785200000326", "English", ["Poetry", "Classic"],
     "A second selection of her compact, dash-filled verse."),
    ("Poems: Series Three", "Dickinson", "9785200000333", "English", ["Poetry"],
     "The third posthumous collection of her poems."),
    ("The Complete Poems", "Dickinson", "9785200000340", "English", ["Poetry", "Classic"],
     "Nearly all of Dickinson's nearly 1,800 poems in a single volume."),
    ("And Then There Were None", "Christie", "9785200000357", "English", ["Mystery", "Classic"],
     "Ten strangers on an island are killed one by one according to a nursery rhyme."),
    ("The Murder of Roger Ackroyd", "Christie", "9785200000364", "English", ["Mystery", "Classic"],
     "Poirot investigates a village murder with a famously surprising solution."),
    ("Death on the Nile", "Christie", "9785200000371", "English", ["Mystery", "Classic"],
     "A honeymoon cruise ends in murder, and Poirot is on board."),
    ("The ABC Murders", "Christie", "9785200000388", "English", ["Mystery"],
     "A killer sends Poirot alphabetical warnings before each crime."),
    ("Murder at the Vicarage", "Christie", "9785200000395", "English", ["Mystery"],
     "Miss Marple's first full-length case begins with a corpse in the vicar's study."),
    ("The Mysterious Affair at Styles", "Christie", "9785200000401", "English", ["Mystery", "Classic"],
     "Poirot's first case: a poisoning at a country house."),
    ("Evil Under the Sun", "Christie", "9785200000418", "English", ["Mystery"],
     "A glamorous actress is found strangled on a seaside resort beach."),
    ("Five Little Pigs", "Christie", "9785200000425", "English", ["Mystery"],
     "Poirot reinvestigates a sixteen-year-old poisoning by interviewing five witnesses."),
    ("The Body in the Library", "Christie", "9785200000432", "English", ["Mystery"],
     "Miss Marple investigates a young woman's body found in a respectable home."),
    ("A Murder Is Announced", "Christie", "9785200000449", "English", ["Mystery"],
     "A newspaper notice promises a murder at a village house, and it happens."),
    ("4.50 from Paddington", "Christie", "9785200000456", "English", ["Mystery"],
     "A woman sees a murder from a passing train and Miss Marple tracks the body."),
    ("The Mirror Crack'd from Side to Side", "Christie", "9785200000463", "English", ["Mystery"],
     "A poisoning at a village party points to a famous actress."),
    ("Cards on the Table", "Christie", "9785200000470", "English", ["Mystery"],
     "Poirot investigates a murder at a bridge party among four suspects."),
    ("Sad Cypress", "Christie", "9785200000487", "English", ["Mystery"],
     "A young woman is accused of poisoning and Poirot must find the real culprit."),
    ("El amor en los tiempos del cólera", "García Márquez", "9785300000011", "Spanish", ["Classic"],
     "Un amor que espera más de cincuenta años para cumplirse en una ciudad del Caribe."),
    ("Crónica de una muerte anunciada", "García Márquez", "9785300000028", "Spanish", ["Classic", "Mystery"],
     "Todo el pueblo sabe que van a matar a Santiago Nasar, pero nadie lo evita."),
    ("El coronel no tiene quien le escriba", "García Márquez", "9785300000035", "Spanish", ["Classic"],
     "Un viejo coronel espera en vano su pensión de veterano."),
    ("El otoño del patriarca", "García Márquez", "9785300000042", "Spanish", ["Classic"],
     "La vida y la soledad de un dictador caribeño eterno."),
    ("Ficciones", "Borges", "9785300000059", "Spanish", ["Classic", "Science Fiction"],
     "Cuentos de laberintos, bibliotecas infinitas y espejos que desafían la realidad."),
    ("El Aleph", "Borges", "9785300000066", "Spanish", ["Classic", "Fantasy"],
     "Relatos sobre el infinito, la memoria y un punto que contiene todo el universo."),
    ("El hacedor", "Borges", "9785300000073", "Spanish", ["Classic", "Poetry"],
     "Breves prosas y poemas sobre la creación y la ceguera."),
    ("Historia universal de la infamia", "Borges", "9785300000080", "Spanish", ["Classic"],
     "Biografías ficticias de bandidos y farsantes famosos."),
    ("Fervor de Buenos Aires", "Borges", "9785300000097", "Spanish", ["Poetry"],
     "El primer libro de poemas de Borges, dedicado a su ciudad."),
    ("Don Quijote de la Mancha", "Cervantes", "9785300000103", "Spanish", ["Classic"],
     "Un hidalgo enloquecido por los libros de caballerías sale con Sancho Panza a vivir aventuras."),
    ("Novelas ejemplares", "Cervantes", "9785300000110", "Spanish", ["Classic"],
     "Doce novelas cortas sobre amor, engaño y justicia."),
    ("La Galatea", "Cervantes", "9785300000127", "Spanish", ["Classic", "Poetry"],
     "Una novela pastoril sobre los amores de pastores en las riberas del Tajo."),
    ("La casa de los espíritus", "Allende", "9785300000134", "Spanish", ["Classic", "Fantasy"],
     "La saga de la familia Trueba a lo largo de varias generaciones y un siglo de historia chilena."),
    ("Eva Luna", "Allende", "9785300000141", "Spanish", ["Classic"],
     "Una joven narradora cuenta su vida desde la pobreza hasta la fama."),
    ("De amor y de sombra", "Allende", "9785300000158", "Spanish", ["Classic"],
     "Una periodista y un fotógrafo descubren un crimen durante una dictadura."),
]

from django.contrib.auth.models import Group, Permission, User

LIBRARIAN_GROUP = "Librarians"
LIBRARIAN_USERNAME = "libby"

class Command(BaseCommand):
    help = "Seed the database with sample catalog data (idempotent)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all catalog data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        # Signals swallow indexing errors, so check up front rather than seed rows that never get indexed.
        if not search.get_client().ping():
            raise CommandError(
                "OpenSearch is unreachable, so seeded books would not be searchable. "
                "Start it with `docker compose up -d`, or run `python manage.py search_index` after seeding."
            )

        password = os.environ.get(SEED_PASSWORD_ENV)
        if not password:
            raise CommandError(
                f"{SEED_PASSWORD_ENV} is not set. It is the password given to every seeded user, "
                f"e.g. `{SEED_PASSWORD_ENV}=... python manage.py seed`."
            )

        if options["reset"]:
            self.reset()

        genres = {n: Genre.objects.get_or_create(name=n)[0] for n in GENRES}
        languages = {n: Language.objects.get_or_create(name=n)[0] for n in LANGUAGES}

        authors: dict[str, Author] = {}
        for first, last, born, died in AUTHORS:
            authors[last], _ = Author.objects.get_or_create(
                first_name=first,
                last_name=last,
                defaults={"date_of_birth": born, "date_of_death": died},
            )

        user_model = get_user_model()
        borrowers = []
        for username, first, last in USERS:
            user, created = user_model.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com"},
            )
            if created:
                user.set_password(password)
                user.save()
            borrowers.append(user)

        permission = Permission.objects.get(
            content_type__app_label="catalog",
            codename="can_mark_returned",
        )

        librarians, _ = Group.objects.get_or_create(name=LIBRARIAN_GROUP)
        librarians.permissions.add(permission)  # add() is idempotent

        librarian, created = User.objects.get_or_create(
            username=LIBRARIAN_USERNAME,
            defaults={"first_name": "Libby", "last_name": "Librarian", "email": "libby@example.com"},
        )
        if created:
            librarian.set_password(password)
            librarian.save()
        librarian.groups.add(librarians)

        today = date.today()
        loans = 0
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
                instance, created = BookInstance.objects.get_or_create(
                    book=book,
                    imprint=f"First edition, copy {copy}",
                    defaults={
                        "status": status,
                        "due_back": today + timedelta(days=7 * copy) if status == "o" else None,
                    },
                )
                copies_created += created

                # Hand on-loan copies out round-robin; leave any existing borrower alone.
                if instance.status == "o" and instance.borrower is None:
                    instance.borrower = borrowers[loans % len(borrowers)]
                    instance.save(update_fields=["borrower"])
                    loans += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Genre.objects.count()} genres, {Language.objects.count()} languages, "
            f"{Author.objects.count()} authors, {Book.objects.count()} books, "
            f"{BookInstance.objects.count()} copies ({copies_created} new), "
            f"{len(borrowers)} users ({loans} loans handed out)."
        ))
        self.stdout.write(f"Seed users: {', '.join(u for u, _, _ in USERS)}, {LIBRARIAN_USERNAME} (password: ${SEED_PASSWORD_ENV})")

    def reset(self) -> None:
        # Children first: Book/BookInstance foreign keys use on_delete=RESTRICT.
        BookInstance.objects.all().delete()
        Book.objects.all().delete()
        Author.objects.all().delete()
        Genre.objects.all().delete()
        Language.objects.all().delete()
        get_user_model().objects.filter(username__in=[u for u, _, _ in USERS]  + [LIBRARIAN_USERNAME]).delete()
        self.stdout.write("Existing catalog data deleted.")
