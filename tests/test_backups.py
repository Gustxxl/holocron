import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import backups

DAY = 86400


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patch = mock.patch.object(backups, 'DIR', self.root / 'backups')
        patch.start()
        self.addCleanup(patch.stop)

    def file(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def copy(self, name, days, size=10):
        backups.DIR.mkdir(parents=True, exist_ok=True)
        f = backups.DIR / name
        f.write_bytes(b'x' * size)
        t = time.time() - days * DAY
        os.utime(f, (t, t))
        return f

    def left(self):
        return sorted(f.name for f in backups.DIR.iterdir())


class Save(Base):
    def test_copy_made(self):
        path = self.file('Board.md', 'one')
        self.assertEqual(backups.save(path).read_text(encoding='utf-8'), 'one')

    def test_every_change_kept(self):
        path = self.file('Board.md', 'one')
        backups.save(path)
        path.write_text('two', encoding='utf-8')
        backups.save(path)
        self.assertEqual(len(self.left()), 2)

    def test_same_content_once(self):
        path = self.file('Board.md', 'one')
        backups.save(path)
        backups.save(path)
        self.assertEqual(len(self.left()), 1)

    def test_same_name_other_folder(self):
        backups.save(self.file('Work/Board.md', 'work'))
        backups.save(self.file('Home/Board.md', 'home'))
        texts = sorted(f.read_text(encoding='utf-8') for f in backups.DIR.iterdir())
        self.assertEqual(texts, ['home', 'work'])

    def test_brackets_in_name(self):
        path = self.file('[draft] Board.md', 'one')
        backups.save(path)
        backups.save(path)
        self.assertEqual(len(self.left()), 1)

    def test_missing_file(self):
        self.assertIsNone(backups.save(self.root / 'nope.md'))


class Prune(Base):
    def test_old_removed(self):
        self.copy('Board.md.aaaa1111.20260801-120000-000000.bak', 40)
        new = self.copy('Board.md.aaaa1111.20261015-120000-000000.bak', 1)
        backups.prune()
        self.assertEqual(self.left(), [new.name])

    def test_last_copy_kept_when_old(self):
        only = self.copy('Board.md.aaaa1111.20260801-120000-000000.bak', 40)
        backups.prune()
        self.assertEqual(self.left(), [only.name])

    def test_legacy_removed_when_old(self):
        self.copy('Board.md', 40)
        backups.prune()
        self.assertEqual(self.left(), [])

    def test_size_limit(self):
        names = [self.copy(f'N{n}.md.aaaa1111.20261010-12000{n}-000000.bak', 5 - n, size=40).name for n in range(5)]
        with mock.patch.object(backups, 'MAX_BYTES', 100):
            backups.prune()
        self.assertEqual(self.left(), names[3:])

    def test_keep_never_removed(self):
        keep = self.copy('Big.md.aaaa1111.20261010-120000-000000.bak', 5, size=500)
        with mock.patch.object(backups, 'MAX_BYTES', 100):
            backups.prune(keep=keep)
        self.assertEqual(self.left(), [keep.name])

    def test_prune_on_save(self):
        self.copy('Old.md.aaaa1111.20260801-120000-000000.bak', 40)
        self.copy('Old.md.aaaa1111.20261015-120000-000000.bak', 1)
        backups.save(self.file('Board.md', 'one'))
        self.assertNotIn('Old.md.aaaa1111.20260801-120000-000000.bak', self.left())
