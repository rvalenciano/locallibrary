import tempfile

from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings


class StaticFileServingTests(SimpleTestCase):
    def test_collected_static_files_are_served_with_debug_off(self):
        with (
            tempfile.TemporaryDirectory() as static_root,
            override_settings(DEBUG=False, STATIC_ROOT=static_root),
        ):
            call_command("collectstatic", interactive=False, verbosity=0)
            client = Client()
            css = client.get("/static/css/styles.css")
            admin_css = client.get("/static/admin/css/base.css")
            self.assertEqual(css.status_code, 200)
            self.assertIn("text/css", css["Content-Type"])
            self.assertEqual(admin_css.status_code, 200)
            css.close()
            admin_css.close()
