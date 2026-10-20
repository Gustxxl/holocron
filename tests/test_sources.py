import copy
import subprocess
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core import settings, sources
from core.sources import cli, registry, remindctl

LISTS = [
    {'id': 'L1', 'overdueCount': 0, 'reminderCount': 3, 'title': 'Work'},
    {'id': 'L2', 'overdueCount': 0, 'reminderCount': 1, 'title': 'Дом🏡'},
    {'id': 'L3', 'overdueCount': 0, 'reminderCount': 0, 'title': 'Empty'},
    {'title': 'no id'},
]

OPEN = [
    {'id': 'A1', 'title': 'Renew domain', 'dueDate': '2026-10-10T07:00:00Z', 'dueDateIsAllDay': False,
     'isCompleted': False, 'listID': 'L1', 'listName': 'Work', 'priority': 'none',
     'locationTrigger': {'address': ' Main 1 ', 'latitude': 1.0, 'longitude': 2.0,
                         'radius': 100, 'proximity': 'arriving'}},
    {'id': 'A2', 'title': 'Buy milk', 'dueDate': '2026-10-12', 'dueDateIsAllDay': True,
     'isCompleted': False, 'listID': 'L2', 'listName': 'Дом🏡', 'priority': 'none', 'notes': ' 2 l '},
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


class RunOk(unittest.TestCase):
    def _run(self, result, found=True):
        with patch('core.sources.cli.shutil.which', return_value='/bin/x' if found else None), \
             patch.object(cli.system, 'run', return_value=result):
            return cli.run_ok('x')

    def test_results(self):
        self.assertFalse(self._run(_done(0, ''), found=False))
        self.assertFalse(self._run(None))
        self.assertFalse(self._run(_done(1, '')))
        self.assertTrue(self._run(_done(0, '')))


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
        self.assertEqual(items['A2']['list_name'], 'Дом🏡')
        self.assertEqual(items['A2']['notes'], '2 l')
        self.assertEqual(items['A3']['title'], '(untitled)')
        self.assertEqual(items['A3']['notes'], '')
        self.assertIsNone(items['A3']['due'])
        self.assertTrue(items['A4']['done'])
        self.assertEqual(items['A1']['place'], 'Main 1')
        self.assertEqual(items['A2']['place'], '')

    def test_not_a_list(self):
        self.assertIsNone(remindctl.parse_lists({'error': 1}))
        self.assertIsNone(remindctl.parse_items(None))

    def test_unavailable_off_macos(self):
        with patch.object(remindctl.system, 'IS_MACOS', False), \
             patch.object(remindctl.cli, 'available', return_value=True):
            self.assertFalse(remindctl.available())


class Changes(unittest.TestCase):
    def test_complete(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            self.assertTrue(remindctl.complete('A1'))
        run.assert_called_once_with('remindctl', 'complete', 'A1')

    def test_add(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=False) as run:
            self.assertFalse(remindctl.add('Buy milk', 'L2'))
        run.assert_called_once_with('remindctl', 'add', '--title', 'Buy milk', '--list-id', 'L2')

    def test_add_place(self):
        place = {'address': 'Main 1', 'radius': 50, 'proximity': 'leaving'}
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            remindctl.add('Lock up', 'L1', place)
        run.assert_called_once_with('remindctl', 'add', '--title', 'Lock up', '--list-id', 'L1',
                                    '--location', 'Main 1', '--radius', '50', '--leaving')

    def test_edit(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            self.assertTrue(remindctl.edit('A1', title='New', notes=''))
        run.assert_called_once_with('remindctl', 'edit', 'A1', '--title', 'New', '--notes', '')

    def test_edit_nothing(self):
        with patch.object(remindctl.cli, 'run_ok') as run:
            self.assertTrue(remindctl.edit('A1'))
        run.assert_not_called()


class Selected(unittest.TestCase):
    LISTS = [{'id': 'L1', 'title': 'A'}, {'id': 'L2', 'title': 'B'}, {'id': 'L3', 'title': 'C'}]

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

    def test_default_falls_back_to_first_selected(self):
        self.store = {'sources': {'remindctl': {'lists': ['L2', 'L3']}}}
        self.assertEqual(sources.default('remindctl', self.LISTS), 'L2')

    def test_default_none_without_lists(self):
        self.assertIsNone(sources.default('remindctl', self.LISTS))

    def test_stored_default(self):
        self.store = {'sources': {'remindctl': {'lists': ['L1', 'L3'], 'default': 'L3'}}}
        self.assertEqual(sources.default('remindctl', self.LISTS), 'L3')

    def test_stored_default_gone_from_reminders(self):
        self.store = {'sources': {'remindctl': {'lists': ['L1', 'L9'], 'default': 'L9'}}}
        self.assertEqual(sources.default('remindctl', self.LISTS), 'L1')

    def test_set_default_shows_hidden_list(self):
        sources.set_default('remindctl', 'L2')
        self.assertEqual(sources.selected('remindctl'), ['L2'])
        self.assertEqual(sources.default('remindctl', self.LISTS), 'L2')

    def test_hiding_default_clears_it(self):
        sources.toggle_list('remindctl', 'L1')
        sources.set_default('remindctl', 'L2')
        sources.toggle_list('remindctl', 'L2')
        self.assertNotIn('default', self.store['sources']['remindctl'])
        self.assertEqual(sources.default('remindctl', self.LISTS), 'L1')

    def test_option(self):
        self.assertEqual(sources.option('ekctl', 'shown', 2), 2)
        sources.set_option('ekctl', 'shown', 5)
        self.assertEqual(sources.option('ekctl', 'shown', 2), 5)
        self.store['sources']['ekctl']['shown'] = 'x'
        self.assertEqual(sources.option('ekctl', 'shown', 2), 2)


from unittest import mock


class RemindersStatus(unittest.TestCase):
    def _status(self, macos='15.1', tools=(), authorized=False):
        with mock.patch('core.sources.macos.platform.mac_ver', return_value=(macos, '', '')), \
             mock.patch('core.sources.cli.available', side_effect=lambda p: p in tools), \
             mock.patch('core.sources.remindctl.authorized', return_value=authorized):
            return remindctl.status()

    def test_old_macos(self):
        self.assertEqual(self._status(macos='13.6'), 'old_macos')

    def test_missing_without_brew(self):
        self.assertEqual(self._status(), 'missing')

    def test_missing(self):
        self.assertEqual(self._status(tools=('brew',)), 'missing')

    def test_denied(self):
        self.assertEqual(self._status(tools=('brew', 'remindctl')), 'denied')

    def test_ready(self):
        self.assertEqual(self._status(tools=('remindctl',), authorized=True), 'ready')


class Registry(unittest.TestCase):
    def _all(self, *found):
        return patch.object(registry, 'ALL', [SimpleNamespace(KIND=kind, NAME=name, supported=lambda ok=ok: ok)
                                              for kind, name, ok in found])

    def test_active_by_kind(self):
        with self._all(('events', 'Calendar', True), ('tasks', 'Reminders', True)):
            self.assertEqual(registry.active('events').NAME, 'Calendar')
            self.assertEqual(registry.active('tasks').NAME, 'Reminders')

    def test_first_supported_wins(self):
        with self._all(('events', 'Calendar', True), ('events', 'Link', True)):
            self.assertEqual(registry.active('events').NAME, 'Calendar')

    def test_skips_unsupported(self):
        with self._all(('events', 'Calendar', False), ('events', 'Link', True)):
            self.assertEqual(registry.active('events').NAME, 'Link')

    def test_none_when_nothing_fits(self):
        with self._all(('events', 'Calendar', False), ('tasks', 'Reminders', True)):
            self.assertIsNone(registry.active('events'))
            self.assertIsNone(registry.active('notes'))

    def test_supported_keeps_order(self):
        with self._all(('tasks', 'Reminders', True), ('events', 'Calendar', False), ('events', 'Link', True)):
            self.assertEqual([s.NAME for s in registry.supported()], ['Reminders', 'Link'])

    def test_nothing_supported(self):
        with self._all(('events', 'Calendar', False)):
            self.assertEqual(registry.supported(), [])

    def test_block(self):
        with self._all(('events', 'Calendar', True)):
            self.assertEqual(registry.block('calendar').NAME, 'Calendar')
            self.assertIsNone(registry.block('reminders'))
            self.assertIsNone(registry.block('schedule'))
            self.assertIsNone(registry.block('weather'))

    def test_blocks_cover_main_screen(self):
        self.assertEqual({*registry.BLOCKS, 'schedule'}, set(settings.HOME_BLOCKS))

    def test_real_sources(self):
        keys = [s.KEY for s in registry.ALL]
        self.assertEqual(len(keys), len(set(keys)))
        for source in registry.ALL:
            with self.subTest(source.NAME):
                self.assertIn(source.KIND, registry.BLOCKS.values())
                for name in ('NAME', 'KEY', 'SETUP', 'LISTS', 'HINT', 'SHOWN', 'AHEAD'):
                    self.assertTrue(hasattr(source, name), name)
                for name in ('supported', 'available', 'authorized', 'lists', 'items'):
                    self.assertTrue(callable(getattr(source, name, None)), name)
