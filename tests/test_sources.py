import copy
import os
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import settings, sources
from core.sources import cli, registry, remindctl, swiftbar

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

    def test_add_due(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            remindctl.add('Check', 'L1', due=datetime(2026, 10, 11, 0, 5))
        run.assert_called_once_with('remindctl', 'add', '--title', 'Check', '--list-id', 'L1',
                                    '--due', '2026-10-11 00:05')

    def test_add_all_day(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            remindctl.add('Renew', 'L1', due=date(2026, 10, 20))
        run.assert_called_once_with('remindctl', 'add', '--title', 'Renew', '--list-id', 'L1',
                                    '--due', '2026-10-20')

    def test_add_place_and_due(self):
        place = {'address': 'Main 1', 'radius': 50, 'proximity': 'leaving'}
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            remindctl.add('Lock up', 'L1', place, datetime(2026, 10, 11, 22, 5))
        run.assert_called_once_with('remindctl', 'add', '--title', 'Lock up', '--list-id', 'L1',
                                    '--location', 'Main 1', '--radius', '50', '--leaving',
                                    '--due', '2026-10-11 22:05')

    def test_edit(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            self.assertTrue(remindctl.edit('A1', title='New', notes=''))
        run.assert_called_once_with('remindctl', 'edit', 'A1', '--title', 'New', '--notes', '')

    def test_reopen(self):
        with patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            self.assertTrue(remindctl.reopen('A1'))
        run.assert_called_once_with('remindctl', 'edit', 'A1', '--incomplete')

    def test_completed(self):
        data = [{'id': 'A9', 'title': 'Alpha', 'isCompleted': True, 'completionDate': '2026-11-22T10:00:00',
                 'listID': 'L1'}]
        with patch.object(remindctl.cli, 'run_json', return_value=data) as run:
            found = remindctl.completed()
        run.assert_called_once_with('remindctl', 'completed', '--json')
        self.assertTrue(found[0]['done'])
        self.assertEqual(found[0]['finished'], datetime(2026, 11, 22, 10, 0))

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

    def test_text(self):
        self.assertEqual(sources.text('swiftbar', 'folder'), '')
        sources.set_option('swiftbar', 'folder', '/Альфа')
        self.assertEqual(sources.text('swiftbar', 'folder'), '/Альфа')
        self.store['sources']['swiftbar']['folder'] = 5
        self.assertEqual(sources.text('swiftbar', 'folder'), '')


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
        keys = [s. KEY for s in registry.ALL]
        self.assertEqual(len(keys), len(set(keys)))
        for source in registry.ALL:
            with self.subTest(source.NAME):
                for name in ('NAME', 'KEY', 'KIND', 'SETUP'):
                    self.assertTrue(hasattr(source, name), name)
                for name in ('supported', 'available', 'status'):
                    self.assertTrue(callable(getattr(source, name, None)), name)

    def test_list_sources(self):
        for source in (s for s in registry. ALL if hasattr(s, 'LISTS')):
            with self.subTest(source.NAME):
                self.assertIn(source.KIND, registry.BLOCKS.values())
                for name in ('HINT', 'SHOWN', 'AHEAD'):
                    self.assertTrue(hasattr(source, name), name)
                for name in ('authorized', 'lists', 'items'):
                    self.assertTrue(callable(getattr(source, name, None)), name)


class Swiftbar(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / 'Plugins'
        self.folder.mkdir()
        self.mine, self.on, self.quits, self.calls = '', False, True, []
        self._patch(patch.object(swiftbar, 'folder', side_effect=lambda: self.folder))
        self._patch(patch.object(swiftbar.sources, 'text', side_effect=lambda key, name: self.mine))
        self._patch(patch.object(swiftbar.system, 'run', side_effect=self._run))
        self._patch(patch.object(swiftbar.time, 'sleep'))
        self.stored = self._patch(patch.object(swiftbar.sources, 'set_option'))

    def _patch(self, patcher):
        found = patcher.start()
        self.addCleanup(patcher.stop)
        return found

    def _run(self, args, timeout=None):
        self.calls.append(args)
        if args[0] == 'osascript':
            if 'quit' in args[2] and self.quits:
                self.on = False
            return _done(0, 'true\n' if self.on else 'false\n')
        return _done(0, '')

    def _defaults(self):
        return [c[1:] for c in self.calls if c[0] == 'defaults']

    def _create(self):
        self.home = self.root / 'SwiftBar'
        with patch.object(swiftbar, 'HOME', str(self.home)), \
             patch.object(swiftbar, 'app', return_value=Path('/A/SwiftBar.app')), \
             patch.object(swiftbar.macos, 'open_url') as self.opened:
            return swiftbar.create()

    def test_create_sets_folder(self):
        self.assertEqual(self._create(), 'ok')
        self.assertTrue(self.home.is_dir())
        self.assertEqual(self._defaults(), [['write', 'com.ameba.SwiftBar', 'PluginDirectory', str(self.home)]])
        self.stored.assert_called_once_with('swiftbar', 'folder', str(self.home))
        self.opened.assert_called_once_with(str(Path('/A/SwiftBar.app')))

    def test_create_quits_app_first(self):
        self.on = True
        self.assertEqual(self._create(), 'ok')
        names = [c[0] for c in self.calls]
        self.assertLess(names.index('osascript'), names.index('defaults'))

    def test_create_waits_for_app(self):
        self.on, self.quits = True, False
        self.assertEqual(self._create(), 'running')
        self.assertFalse(self.home.exists())
        self.assertEqual(self._defaults(), [])

    def test_create_keeps_existing_folder(self):
        (self.root / 'SwiftBar').mkdir()
        self.assertEqual(self._create(), 'ok')
        self.stored.assert_not_called()

    def test_remove_tidies_own_folder(self):
        self.mine = str(self.folder)
        swiftbar.add()
        (self.folder / '.DS_Store').touch()
        self.assertTrue(swiftbar.owned())
        self.assertTrue(swiftbar.remove())
        self.assertFalse(self.folder.exists())
        self.assertEqual(self._defaults(), [['delete', 'com.ameba.SwiftBar', 'PluginDirectory']])
        self.stored.assert_called_once_with('swiftbar', 'folder', '')

    def test_remove_keeps_other_plugins(self):
        self.mine = str(self.folder)
        swiftbar.add()
        (self.folder / 'Alpha.1m.sh').touch()
        self.assertFalse(swiftbar.owned())
        self.assertTrue(swiftbar.remove())
        self.assertEqual(os.listdir(self.folder), ['Alpha.1m.sh'])
        self.assertEqual(self._defaults(), [])

    def test_remove_keeps_foreign_folder(self):
        swiftbar.add()
        self.assertFalse(swiftbar.owned())
        self.assertTrue(swiftbar.remove())
        self.assertTrue(self.folder.is_dir())
        self.stored.assert_not_called()

    def _start(self, state='ready', app=True):
        with patch.object(swiftbar, 'status', return_value=state), \
             patch.object(swiftbar, 'app', return_value=Path('/A/SwiftBar.app') if app else None):
            return swiftbar.start()

    def test_start_opens_in_background(self):
        self.assertTrue(self._start())
        self.assertIn(['open', '-g', str(Path('/A/SwiftBar.app'))], self.calls)

    def test_start_leaves_running_app(self):
        self.on = True
        self.assertFalse(self._start())
        self.assertFalse(any(c[0] == 'open' for c in self.calls))

    def test_start_needs_plugin(self):
        self.assertFalse(self._start(state='off'))
        self.assertEqual(self.calls, [])

    def _finish(self, opened, mine):
        self.mine, self.on = (str(self.folder) if mine else ''), True
        swiftbar.add()
        swiftbar.finish(opened)
        return self.on

    def test_finish_quits_own_folder(self):
        self.assertFalse(self._finish(opened=False, mine=True))

    def test_finish_quits_what_it_opened(self):
        self.assertFalse(self._finish(opened=True, mine=False))

    def test_finish_leaves_foreign_app(self):
        self.assertTrue(self._finish(opened=False, mine=False))
        self.assertEqual([c for c in self.calls if c[0] == 'osascript'], [])

    def test_remove_waits_for_app(self):
        self.mine, self.on, self.quits = str(self.folder), True, False
        swiftbar.add()
        self.assertFalse(swiftbar.remove())
        self.assertTrue(swiftbar.added())

    def test_add_writes_script(self):
        self.assertTrue(swiftbar.add())
        path = self.folder / swiftbar.FILE
        self.assertEqual(path.read_text(encoding='utf-8'), swiftbar.script())
        self.assertTrue(os.access(path, os.X_OK))
        self.assertEqual(os.listdir(self.folder), [swiftbar.FILE])
        self.assertTrue(swiftbar.added())

    def test_add_replaces_stale_copy(self):
        (self.folder / swiftbar.FILE).write_text('Alpha', encoding='utf-8')
        self.assertFalse(swiftbar.added())
        self.assertTrue(swiftbar.add())
        self.assertTrue(swiftbar.added())

    def test_remove(self):
        swiftbar.add()
        self.assertTrue(swiftbar.remove())
        self.assertEqual(os.listdir(self.folder), [])
        self.assertFalse(swiftbar.added())

    def test_nothing_without_folder(self):
        self.folder = None
        self.assertFalse(swiftbar.add())
        self.assertFalse(swiftbar.remove())
        self.assertFalse(swiftbar.added())

    def test_script_runs_this_copy(self):
        with patch.object(swiftbar.sys, 'executable', '/Альфа dir/python'), \
             patch.object(swiftbar, 'MAIN', '/Альфа dir/main.py'):
            lines = swiftbar.script().splitlines()
        self.assertEqual(lines[0], '#!/bin/sh')
        self.assertIn('# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>', lines)
        self.assertEqual(lines[-1], "exec '/Альфа dir/python' '/Альфа dir/main.py' --bar")

    def test_off_macos(self):
        swiftbar.add()
        with patch.object(swiftbar.system, 'IS_MACOS', False):
            self.assertFalse(swiftbar.available())
            self.assertNotIn(swiftbar, registry.supported())


class SwiftbarSetup(unittest.TestCase):
    def _folder(self, result):
        with patch.object(swiftbar.system, 'run', return_value=result) as self.run:
            return swiftbar.folder()

    def test_folder_from_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._folder(_done(0, f'{tmp}\n')), Path(tmp))
        self.run.assert_called_once_with(['defaults', 'read', 'com.ameba.SwiftBar', 'PluginDirectory'],
                                         timeout=cli.TIMEOUT)

    def test_no_folder(self):
        for result in (None, _done(1, ''), _done(0, '\n'), _done(0, '/no/such/dir\n')):
            with self.subTest(result=result):
                self.assertIsNone(self._folder(result))

    def test_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'SwiftBar.app').mkdir()
            with patch.object(swiftbar, 'APPS', ('/no/such', tmp)):
                self.assertEqual(swiftbar.app(), Path(tmp) / 'SwiftBar.app')
            with patch.object(swiftbar, 'APPS', ('/no/such',)):
                self.assertIsNone(swiftbar.app())

    def _status(self, version='15.1', app=True, folder=True, added=False):
        with patch('core.sources.macos.platform.mac_ver', return_value=(version, '', '')), \
             patch.object(swiftbar, 'app', return_value=Path('/A/SwiftBar.app') if app else None), \
             patch.object(swiftbar, 'folder', return_value=Path('/P') if folder else None), \
             patch.object(swiftbar, 'added', return_value=added):
            return swiftbar.status()

    def test_status_steps(self):
        self.assertEqual(self._status(version='11.7'), 'old_macos')
        self.assertEqual(self._status(app=False), 'missing')
        self.assertEqual(self._status(folder=False), 'no_folder')
        self.assertEqual(self._status(), 'off')
        self.assertEqual(self._status(added=True), 'ready')


class SwiftbarRender(unittest.TestCase):
    def _lines(self, on=False, title='', alert=False, duty='', groups=()):
        with patch.object(swiftbar.sys, 'executable', '/Альфа/python'), \
             patch.object(swiftbar, 'MAIN', '/Альфа/main.py'):
            return swiftbar.render(on, title, alert, duty, list(groups)).splitlines()

    def test_calm_shows_icon(self):
        self.assertEqual(self._lines(), ['◇ | length=40 symbolize=false emojize=false'])

    def test_duty_icon(self):
        self.assertEqual(self._lines(on=True)[0], '● | length=40 symbolize=false emojize=false')

    def test_alert_is_red(self):
        self.assertEqual(self._lines(title='09:00 Alpha', alert=True)[0],
                         '◇ 09:00 Alpha | length=40 symbolize=false emojize=false color=#af5f5f')

    def test_layout(self):
        lines = self._lines(duty='● ON DUTY', groups=[('overdue', [('Todo', True, None)]),
                                                       ('today', [('09:00 Alpha', False, None)])])
        self.assertEqual(lines[1:], [
            '---', '● ON DUTY | symbolize=false emojize=false', '---',
            'overdue | size=12 symbolize=false emojize=false',
            'Todo | symbolize=false emojize=false color=#af5f5f',
            'today | size=12 symbolize=false emojize=false',
            '09:00 Alpha | symbolize=false emojize=false',
        ])

    def test_done_action(self):
        line = self._lines(groups=[('today', [('09:00 Alpha', False, ('done', 'A-1'))])])[-1]
        self.assertEqual(line, '09:00 Alpha | bash="/Альфа/python" param1="/Альфа/main.py" param2=--done '
                               'param3=A-1 terminal=false refresh=true symbolize=false emojize=false')

    def test_undo_action(self):
        line = self._lines(groups=[('done today', [('✓ 09:00 Alpha', False, ('undo', 'A-1'))])])[-1]
        self.assertIn(' param2=--undo param3=A-1 ', line)
        self.assertNotIn('checked', line)

    def test_strange_id_has_no_action(self):
        line = self._lines(groups=[('today', [('09:00 Alpha', False, ('done', 'A1 color=red'))])])[-1]
        self.assertEqual(line, '09:00 Alpha | symbolize=false emojize=false')

    def test_text_cannot_break_menu(self):
        lines = self._lines(title='--- Alpha | color=red', groups=[('---', [('Альфа\n---\nTodo', False, None)])])
        self.assertEqual(lines[0].split(' | ')[0], '◇ --- Alpha ¦ color=red')
        self.assertEqual(lines[2], ' | size=12 symbolize=false emojize=false')
        self.assertEqual(lines[3], 'Альфа --- Todo | symbolize=false emojize=false')
        self.assertEqual(sum(line == '---' for line in lines), 1)


class SwiftbarAsk(unittest.TestCase):
    def _ask(self, result):
        with patch.object(swiftbar.system, 'run', return_value=result) as self.run:
            return swiftbar.ask('Альфа "x"', 'Todo')

    def test_text_returned(self):
        self.assertEqual(self._ask(_done(0, 'Alpha 09:00\n')), 'Alpha 09:00')
        args = self.run.call_args.args[0]
        self.assertEqual(args[0], 'osascript')
        self.assertEqual(args[-2:], ['Альфа "x"', 'Todo'])

    def test_cancel_or_failure(self):
        for result in (None, _done(1, '')):
            with self.subTest(result=result):
                self.assertEqual(self._ask(result), '')

    def test_new_reminder_item(self):
        with patch.object(swiftbar.sys, 'executable', '/Альфа/python'), \
             patch.object(swiftbar, 'MAIN', '/Альфа/main.py'):
            lines = swiftbar.render(False, '', False, '', [], True).splitlines()
            calm = swiftbar.render(False, '', False, '', []).splitlines()
        self.assertEqual(lines[-2:], ['---', '+ New reminder | bash="/Альфа/python" param1="/Альфа/main.py" '
                                             'param2=--new terminal=false refresh=true symbolize=false emojize=false'])
        self.assertFalse(any('New reminder' in line for line in calm))


class MenuBarCheck(unittest.TestCase):
    def test_check_names_app(self):
        from core import diagnostics
        source = SimpleNamespace(NAME='Menu bar', APP='SwiftBar', available=lambda: True)
        self.assertEqual(diagnostics._tool(source), 'SwiftBar')
        self.assertIsNone(diagnostics._tool(SimpleNamespace(NAME='Menu bar', APP='SwiftBar', available=lambda: False)))
