import os
import runpy
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SETTINGS_PATH = str(Path(__file__).parent / "settings.py")


def load_databases(database_url: str | None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env["SECRET_KEY"] = "test-secret-key"
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    with mock.patch.dict(os.environ, env, clear=True):
        return runpy.run_path(SETTINGS_PATH)["DATABASES"]


class DatabaseSettingsTests(SimpleTestCase):
    def test_defaults_to_sqlite_when_database_url_unset(self):
        default = load_databases(None)["default"]
        self.assertEqual(default["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(Path(default["NAME"]).name, "db.sqlite3")

    def test_database_url_selects_postgres(self):
        default = load_databases("postgres://user:secret@db.example:5433/library")[
            "default"
        ]
        self.assertEqual(default["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(default["NAME"], "library")
        self.assertEqual(default["USER"], "user")
        self.assertEqual(default["PASSWORD"], "secret")
        self.assertEqual(default["HOST"], "db.example")
        self.assertEqual(default["PORT"], 5433)

    def test_postgres_gets_a_connect_timeout(self):
        default = load_databases("postgres://user:secret@db.example:5433/library")[
            "default"
        ]
        self.assertEqual(default["OPTIONS"]["connect_timeout"], 5)

    def test_sqlite_gets_no_connect_timeout(self):
        default = load_databases(None)["default"]
        self.assertNotIn("connect_timeout", default.get("OPTIONS", {}))
