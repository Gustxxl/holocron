import copy
import subprocess
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core import sources
from core.sources import cli, remindctl

LISTS = [
    {'id': 'L1', 'overdueCount': 0, 'reminderCount': 3, 'title': 'Work'},
    {'id': 'L2', 'overdueCount': 0, 'reminderCount': 1, 'title': 'Дом🏡'},
    {'id': 'L3', 'overdueCount': 0, 'reminderCount': 0, 'title': 'Empty'},
    {'title': 'no id'},
]

OPEN = [
    {'id': 'A1', 'title': 'Renew domain', 'dueDate': '2026-10-10T07:00:00Z', 'dueDateIsAllDay': False,
     'isCompleted': False, 'listID': 'L1', 'listName': 'Work', 'priority': 'none'},
    {'id': 'A2', 'title': 'Buy milk', 'dueDate': '2026-10-12', 'dueDateIsAllDay': True,
     'isCompleted': False, 'listID': 'L2', 'listName': 'Дом🏡', 'priority': 'none'},
    {'id': 'A3', 'title': '  ', 'dueDateIsAllDay': False, 'isCompleted': False, 'listID': 'L1'},
    {'id': 'A4', 'title': 'Done one', 'dueDateIsAllDay': False, 'isCompleted': True, 'listID': 'L1'},
    {'title': 'no id'},
    'junk',
]


def _done(code, out):
    return subprocess.CompletedProcess([], code, out, '')


class RunJson(unittest.TestCase):
    def _run(self, result, found=True):
        with patch('core.sources.cli.shutil.which', return_value='/bin/x' if found else None), \
             patch.object(cli.system, 'run', return_value=result):
            return cli.run_json('x')

    def test_missing_program(self):
        self.assertIsNone(self._run(_done(0, '[]'), found=False))

    def test_failed_run(self):
        self.assertIsNone(self._run(None))
        self.assertIsNone(self._run(_done(1, '[]')))

    def test_broken_json(self):
        self.assertIsNone(self._run(_done(0, '[{')))

    def test_json(self):
        self.assertEqual(self._run(_done(0, '[1]')), [1])


class ParseTime(unittest.TestCase):
    def test_date_only(self):
        self.assertEqual(cli.parse_time('2026-10-12'), datetime(2026, 10, 12))

    def test_local(self):
        self.assertEqual(cli.parse_time('2026-10-12T09:30:00'), datetime(2026, 10, 12, 9, 30))

    def test_utc_to_local(self):
        expected = datetime(2026, 10, 10, 7, tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        self.assertEqual(cli.parse_time('2026-10-10T07:00:00Z'), expected)

    def test_garbage(self):
        for value in (None, '', 'tomorrow', 5):
            self.assertIsNone(cli.parse_time(value))


class Remindctl(unittest.TestCase):
    def test_lists(self):
        self.assertEqual(remindctl.parse_lists(LISTS), [
            {'id': 'L1', 'title': 'Work'},
            {'id': 'L2', 'title': 'Дом🏡'},
            {'id': 'L3', 'title': 'Empty'},
        ])

    def test_items(self):
        items = {t['id']: t for t in remindctl.parse_items(OPEN)}
        self.assertEqual(sorted(items), ['A1', 'A2', 'A3', 'A4'])
        self.assertEqual(items['A2']['due'], datetime(2026, 10, 12))
        self.assertTrue(items['A2']['all_day'])
        self.assertEqual(items['A2']['list'], 'L2')
        self.assertEqual(items['A3']['title'], '(untitled)')
        self.assertIsNone(items['A3']['due'])
        self.assertTrue(items['A4']['done'])
        self.assertEqual(items['A2']['list_name'], 'Дом🏡')

    def test_not_a_list(self):
        self.assertIsNone(remindctl.parse_lists({'error': 1}))
        self.assertIsNone(remindctl.parse_items(None))

    def test_unavailable_off_macos(self):
        with patch.object(remindctl.system, 'IS_MACOS', False), \
             patch.object(remindctl.cli, 'available', return_value=True):
            self.assertFalse(remindctl.available())


class Selected(unittest.TestCase):
    def setUp(self):
        self.store = {}
        load = patch.object(sources.config, 'load', side_effect=lambda: copy.deepcopy(self.store))
        save = patch.object(sources.config, 'save', side_effect=self._save)
        load.start()
        save.start()
        self.addCleanup(load.stop)
        self.addCleanup(save.stop)

    def _save(self, cfg):
        self.store.clear()
        self.store.update(copy.deepcopy(cfg))

    def test_nothing_by_default(self):
        self.assertEqual(sources.selected('remindctl'), [])

    def test_garbage_ignored(self):
        for junk in ([], 'x', {'remindctl': 'x'}, {'remindctl': {'lists': 'x'}}):
            self.store = {'sources': junk}
            self.assertEqual(sources.selected('remindctl'), [])

    def test_only_strings_kept(self):
        self.store = {'sources': {'remindctl': {'lists': [1, None, 'L1']}}}
        self.assertEqual(sources.selected('remindctl'), ['L1'])

    def test_toggle(self):
        self.store = {'sources': 'broken', 'operator_name': 'me'}
        self.assertTrue(sources.toggle_list('remindctl', 'L1'))
        self.assertEqual(sources.selected('remindctl'), ['L1'])
        self.assertFalse(sources.toggle_list('remindctl', 'L1'))
        self.assertEqual(sources.selected('remindctl'), [])
        self.assertEqual(self.store['operator_name'], 'me')
