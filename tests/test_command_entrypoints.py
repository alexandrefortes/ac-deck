"""As entradas estáveis funcionam fora do checkout sem abrir menu ou jogo."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CommandEntrypointTests(unittest.TestCase):
    def run_command(self, name, *args):
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        with tempfile.TemporaryDirectory(prefix='external command espaço-') as folder:
            return subprocess.run([sys.executable, '-B', '-X', 'utf8',
                str(ROOT/'scripts'/name), *args], cwd=folder, env=environment,
                text=True, encoding='utf-8', capture_output=True, timeout=20)

    def test_existing_help_is_available_from_an_unrelated_directory(self):
        for name in ('jogo_deck.py', 'pratica_deck.py'):
            with self.subTest(command=name):
                result = self.run_command(name, '--help')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('preparar', result.stdout)
                self.assertIn('steam', result.stdout)
                self.assertNotIn('Traceback', result.stderr)

    def test_invalid_arguments_keep_argparse_failure_from_outside_checkout(self):
        for name in ('jogo_deck.py', 'pratica_deck.py'):
            with self.subTest(command=name):
                result = self.run_command(name, 'invalid-command')
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn('invalid-command', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
