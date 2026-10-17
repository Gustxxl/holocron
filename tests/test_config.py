import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import backups, config


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.path = root / 'data' / 'config.json'
        patches = [
            mock.patch.object(config, 'DATA_DIR', str(root / 'data')),
            mock.patch.object(config, 'CONFIG', self.path),
            mock.patch.object(backups, 'DIR', root / 'backups'),
            mock.patch.object(config, 'broken', None),
            mock.patch.object(config, 'last', None),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, text):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding='utf-8')

    def copies(self):
        if not backups.DIR.exists():
            return []
        return [f.read_text(encoding='utf-8') for f in backups.DIR.iterdir()]


class Load(Base):
    def test_missing_gives_defaults(self):
        self.assertEqual(config.load(), config.DEFAULTS)

    def test_reads_values(self):
        self.write(json.dumps({'operator_name': 'tester'}))
        self.assertEqual(config.load()['operator_name'], 'tester')

    def test_broken_is_backed_up(self):
        self.write('{"operator_name": "tester",')
        cfg = config.load()
        self.assertEqual(cfg, config.DEFAULTS)
        self.assertEqual(self.copies(), ['{"operator_name": "tester",'])
        self.assertTrue(config.broken.endswith('.bak'))

    def test_not_an_object(self):
        self.write('[]')
        self.assertEqual(config.load(), config.DEFAULTS)
        self.assertEqual(self.copies(), ['[]'])

    def test_broken_backed_up_once(self):
        self.write('{')
        config.load()
        config.load()
        self.assertEqual(len(self.copies()), 1)

    def test_keeps_last_good(self):
        self.write(json.dumps({'operator_name': 'tester'}))
        config.load()
        self.write('{')
        self.assertEqual(config.load()['operator_name'], 'tester')

    def test_old_settings_survive_save(self):
        self.write('{"operator_name": "tester",')
        config.save(config.load())
        self.assertEqual(self.copies(), ['{"operator_name": "tester",'])

    def test_valid_not_flagged(self):
        self.write(json.dumps({'operator_name': 'tester'}))
        config.load()
        self.assertIsNone(config.broken)

    def test_no_print_on_load(self):
        self.write('{')
        with mock.patch('builtins.print') as out:
            for _ in range(3):
                config.load()
        out.assert_not_called()

    def test_repaired_from_last(self):
        self.write(json.dumps({'operator_name': 'tester'}))
        config.load()
        self.write('{"operator_name": "tester",')
        self.assertEqual(config.load()['operator_name'], 'tester')
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), {**config.DEFAULTS, 'operator_name': 'tester'})
        self.assertEqual(self.copies(), ['{"operator_name": "tester",'])
        self.assertIsNone(config.broken)

    def test_broken_on_start_untouched(self):
        self.write('{')
        config.load()
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{')


class Save(Base):
    def test_roundtrip(self):
        config.save({'operator_name': 'tester', 'favorites': [['/x/a.md', 'a1']]})
        self.assertEqual(config.load()['favorites'], [['/x/a.md', 'a1']])

    def test_unicode(self):
        config.save({'operator_name': 'тест ✓'})
        self.assertIn('тест ✓', self.path.read_text(encoding='utf-8'))

    def test_failed_write_keeps_old(self):
        self.write(json.dumps({'operator_name': 'old'}))
        with mock.patch.object(config.os, 'replace', side_effect=OSError('disk full')), \
             mock.patch('builtins.print'):
            config.save({'operator_name': 'new'})
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['operator_name'], 'old')
        self.assertFalse(self.path.with_suffix('.json.tmp').exists())


if __name__ == '__main__':
    unittest.main()
