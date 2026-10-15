import unittest
from datetime import datetime, timezone
from unittest import mock

from core import clocks, zones

HAS_DB = zones.get('Europe/Moscow') is not None


class Store(unittest.TestCase):
    def setUp(self):
        self.cfg = {}
        for name, fn in (('load', lambda: dict(self.cfg)), ('save', self.cfg.update)):
            patch = mock.patch.object(clocks.config, name, side_effect=fn)
            patch.start()
            self.addCleanup(patch.stop)

    def test_add_with_name(self):
        clocks.add('Asia/Yekaterinburg', '  Perm  ')
        self.assertEqual(clocks.load(), [{'name': 'Perm', 'zone': 'Asia/Yekaterinburg'}])

    def test_add_default_name(self):
        clocks.add('America/New_York')
        self.assertEqual(clocks.load()[0]['name'], 'New York')

    def test_bad_zone_refused(self):
        self.assertFalse(clocks.add('../etc'))
        self.assertEqual(clocks.load(), [])

    def test_remove(self):
        clocks.add('Europe/Moscow')
        clocks.add('Asia/Yekaterinburg', 'Perm')
        self.assertTrue(clocks.remove(1))
        self.assertEqual([c['name'] for c in clocks.load()], ['Perm'])
        self.assertFalse(clocks.remove(5))

    def test_garbage_dropped(self):
        self.cfg['clocks'] = ['x', {'zone': 5}, {'name': 'A'}, {'name': 3, 'zone': 'Europe/Moscow'}]
        self.assertEqual(clocks.load(), [{'name': 'Moscow', 'zone': 'Europe/Moscow'}])

    def test_long_name_cut(self):
        clocks.add('Europe/Moscow', 'x' * 100)
        self.assertEqual(len(clocks.load()[0]['name']), clocks.NAME_MAX)


@unittest.skipUnless(HAS_DB, 'no time zone database')
class Line(unittest.TestCase):
    NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

    def test_line(self):
        items = [{'name': 'Moscow', 'zone': 'Europe/Moscow'}, {'name': 'Perm', 'zone': 'Asia/Yekaterinburg'}]
        self.assertEqual(clocks.line(items, self.NOW), 'Moscow 15:00   Perm 17:00')

    def test_unknown_zone_skipped(self):
        self.assertEqual(clocks.line([{'name': 'X', 'zone': 'Nowhere/City'}], self.NOW), '')
