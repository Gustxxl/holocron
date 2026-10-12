import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.archives import vault as vault_mod

FILES = ('a.md', 'Work/b.md', 'Work/Old/c.md', 'Old/d.md', 'Old/Notes/g.md', '.trash/e.md', '.obsidian/f.md')


class Exclude(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.vault = self.root / 'Vault'
        for rel in FILES:
            path = self.vault / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('text', encoding='utf-8')

    def patched(self, exclude=(), notes=''):
        return (
            mock.patch.object(vault_mod, 'vault_path', return_value=str(self.vault)),
            mock.patch.object(vault_mod, 'new_cases_path', return_value=notes),
            mock.patch.object(vault_mod, 'vault_exclude', return_value=list(exclude)),
        )

    def load(self, exclude=(), notes=''):
        a, b, c = self.patched(exclude, notes)
        with a, b, c:
            v = vault_mod.Vault()
            v.load()
        return sorted(case['filename'] for case in v._cases)

    def relative(self, folder):
        a, b, c = self.patched()
        with a, b, c:
            return vault_mod.relative(folder)

    def test_hidden_skipped(self):
        self.assertEqual(self.load(), ['a', 'b', 'c', 'd', 'g'])

    def test_excluded(self):
        self.assertEqual(self.load(['Old']), ['a', 'b', 'c'])

    def test_nested(self):
        self.assertEqual(self.load(['Work/Old']), ['a', 'b', 'd', 'g'])

    def test_notes_inside_excluded(self):
        self.assertEqual(self.load(['Old'], str(self.vault / 'Old' / 'Notes')), ['a', 'b', 'c', 'g'])

    def test_notes_same_as_vault(self):
        self.assertEqual(self.load(['Old'], str(self.vault)), ['a', 'b', 'c'])

    def test_relative_absolute(self):
        self.assertEqual(self.relative(str(self.vault / 'Work' / 'Old')), 'Work/Old')

    def test_relative_short(self):
        self.assertEqual(self.relative('Work'), 'Work')

    def test_relative_outside(self):
        self.assertIsNone(self.relative(str(self.root)))

    def test_relative_vault_itself(self):
        self.assertIsNone(self.relative(str(self.vault)))

    def test_relative_missing(self):
        self.assertIsNone(self.relative('Nope'))
        self.assertIsNone(self.relative(''))


        class Folders(unittest.TestCase):
            def test_list_and_counts(self):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    for name in ('Work', 'Personal', 'Old', '.obsidian'):
                        (root / name).mkdir()
                    cases = [{'archive': 'Vault', 'filepath': str(root / rel)}
                             for rel in ('Work/a.md', 'Work/Logs/b.md', 'Personal/c.md', 'top.md')]
                    rows = vault_mod.folders(root, ['Old', 'Work/Logs'], cases)
                self.assertEqual(rows, [('Old', None), ('Personal', 1), ('Work', 2), ('Work/Logs', None)])

            def test_missing_root(self):
                self.assertEqual(vault_mod.folders('/nowhere/at/all', [], []), [])


if __name__ == '__main__':
    unittest.main()
