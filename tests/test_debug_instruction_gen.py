import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import build_task as task


class DebugInstructionTests(unittest.TestCase):
    def run_preview(self, *args, cwd):
        return subprocess.run(
            [sys.executable, str(task.ROOT / 'scripts/build_task.py'), *args],
            cwd=cwd, text=True, capture_output=True)

    def test_seeded_cli_is_reproducible_and_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.run_preview('--debug-instruction-gen', '0', cwd=directory)
            again = self.run_preview('--debug-instruction-gen', '0', cwd=directory)
            different = self.run_preview('--debug-instruction-gen', '-17', cwd=directory)
            for result in (first, again, different):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertEqual(len(result.stdout.splitlines()), 100)
            self.assertEqual(first.stdout, again.stdout)
            self.assertNotEqual(first.stdout, different.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])
        expected = task.generate_directions(random.Random(0))
        self.assertEqual(first.stdout.splitlines(), [sentence for _, sentence in expected])
        parse = task.direction_parser()
        decoded = [parse(sentence) for sentence in first.stdout.splitlines()]
        self.assertTrue(all(decoded))
        self.assertEqual({row[0] for row in decoded}, {task.filename(n) for n in range(1, 101)})
        self.assertEqual(sorted(row[1] for row in decoded), list(range(100)))
        self.assertEqual(sorted(row[2] for row in decoded), list(range(100)))

    def test_preview_without_site_packages(self):
        # -S hides installed third-party packages, even in a populated venv.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-S', str(task.ROOT / 'scripts/build_task.py'),
                 '--debug-instruction-gen', '42'],
                cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 100)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_cli_usage_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for args in ([], ['--debug-instruction-gen'],
                         ['--debug-instruction-gen', 'no-seed'],
                         ['verify', '--debug-instruction-gen', '42'],
                         ['generate', '--debug-instruction-gen', '42']):
                with self.subTest(args=args):
                    result = self.run_preview(*args, cwd=directory)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn('error:', result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])
