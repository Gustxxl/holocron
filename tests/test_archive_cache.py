import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.archives import vault as vault_mod


class Cache(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.vault = Path(tmp.name).resolve()
        self.a = self.vault / 'a.md'
        self.a.write_text('alpha', encoding='utf-8')
        (self.vault / 'b.md').write_text('beta', encoding='utf-8')
        for name, value in (('vault_path', str(self.vault)), ('new_cases_path', ''), ('vault_exclude', [])):
            patch = mock.patch.object(vault_mod, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)
        self.v = vault_mod.Vault()
        self.v.load()

    def find(self, name):
        return next((c for c in self.v._cases if c['filename'] == name), None)

    def names(self):
        return sorted(c['filename'] for c in self.v._cases)

    def rewrite(self, text, shift_ns):
        st = self.a.stat()
        self.a.write_text(text, encoding='utf-8')
        os.utime(self.a, ns=(st.st_atime_ns, st.st_mtime_ns + shift_ns))

    def test_unchanged_reused(self):
        before = self.find('a')
        self.v.load()
        self.assertIs(self.find('a'), before)

    def test_changed_size(self):
        self.a.write_text('alpha and more', encoding='utf-8')
        self.v.load()
        self.assertEqual(self.find('a')['text'], 'alpha and more')

    def test_same_size_new_time(self):
        self.rewrite('omega', 2_000_000_000)
        self.v.load()
        self.assertEqual(self.find('a')['text'], 'omega')

    def test_same_size_same_time_needs_force(self):
        before = self.find('a')
        self.rewrite('omega', 0)
        self.v.load()
        self.assertIs(self.find('a'), before)
        self.v.load(force=True)
        self.assertEqual(self.find('a')['text'], 'omega')

    def test_added_and_removed(self):
        (self.vault / 'c.md').write_text('gamma', encoding='utf-8')
        (self.vault / 'b.md').unlink()
        self.v.load()
        self.assertEqual(self.names(), ['a', 'c'])

    def test_excluded_dropped(self):
        (self.vault / 'Old').mkdir()
        (self.vault / 'Old' / 'd.md').write_text('delta', encoding='utf-8')
        self.v.load()
        self.assertEqual(self.names(), ['a', 'b', 'd'])
        with mock.patch.object(vault_mod, 'vault_exclude', return_value=['Old']):
            self.v.load()
        self.assertEqual(self.names(), ['a', 'b'])

    def test_empty_loaded_once(self):
        for f in self.vault.glob('*.md'):
            f.unlink()
        v = vault_mod.Vault()
        with mock.patch.object(v, '_load', wraps=v._load) as load:
            v.load_cases()
            v.load_cases()
        self.assertEqual(load.call_count, 1)


if __name__ == '__main__':
    unittest.main()
