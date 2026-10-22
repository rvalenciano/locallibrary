import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent


def run_clean(args: list[str], **env: str) -> subprocess.CompletedProcess[str]:
    """Run Python in a child process whose environment has only `env` for the app's variables."""
    clean = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(('DJANGO_', 'SECRET_KEY')) and k != 'DATABASE_URL'
    }
    clean.update(env)
    return subprocess.run([sys.executable, *args], cwd=BASE_DIR, env=clean, capture_output=True, text=True, check=False)


def load_settings(**env: str) -> subprocess.CompletedProcess[str]:
    """Import the settings module in a clean process with only `env` set."""
    code = (
        'import json; from locallibrary import settings as s; '
        'print(json.dumps({"debug": s.DEBUG, "key": s.SECRET_KEY, "hosts": s.ALLOWED_HOSTS, '
        '"csrf": s.CSRF_TRUSTED_ORIGINS, "proto": getattr(s, "SECURE_PROXY_SSL_HEADER", None)}))'
    )
    return run_clean(['-c', code], **env)


def manage(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """Run manage.py in a clean process with only `env` set."""
    return run_clean(['manage.py', *args], **env)


class EnvDrivenSettingsTests(SimpleTestCase):
    def test_debug_off_without_secret_key_fails_at_startup(self) -> None:
        result = load_settings()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY', result.stderr)

    def test_empty_secret_key_is_treated_as_unset(self) -> None:
        self.assertNotEqual(load_settings(SECRET_KEY='').returncode, 0)
        result = load_settings(SECRET_KEY='', DJANGO_DEBUG='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['key'].startswith('django-insecure-'))

    def test_debug_off_with_secret_key_uses_env_values(self) -> None:
        result = load_settings(
            SECRET_KEY='s3cret',
            DJANGO_ALLOWED_HOSTS='a.example.com, b.example.com',
            DJANGO_CSRF_TRUSTED_ORIGINS='https://a.example.com,https://b.example.com',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['debug'])
        self.assertEqual(data['key'], 's3cret')
        self.assertEqual(data['hosts'], ['a.example.com', 'b.example.com'])
        self.assertEqual(data['csrf'], ['https://a.example.com', 'https://b.example.com'])
        self.assertIsNone(data['proto'])

    def test_debug_enabled_explicitly_allows_insecure_dev_key(self) -> None:
        result = load_settings(DJANGO_DEBUG='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['debug'])
        self.assertTrue(data['key'].startswith('django-insecure-'))

    def test_manage_py_runs_any_command_in_dev_mode_with_no_env(self) -> None:
        result = manage('check')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manage_py_explicit_debug_off_without_secret_key_fails_fast(self) -> None:
        result = manage('check', DJANGO_DEBUG='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY', result.stderr)

    def test_proxy_proto_header_is_opt_in(self) -> None:
        result = load_settings(SECRET_KEY='k', DJANGO_TRUST_PROXY_PROTO='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['proto'], ['HTTP_X_FORWARDED_PROTO', 'https'])
