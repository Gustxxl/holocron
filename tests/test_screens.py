import io
import re
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from screens import (diagnostics_screen, favorites_screen, help_screen, keeper_screen,
                     schedule_screen, schedule_settings_screen, settings_screen,
                     tasks_screen, waypoints_screen)

LEAK = re.compile(r"\[\('")


class _Stop(Exception):
    pass


class Screen(unittest.TestCase):
    def open(self, module, call, inputs=(), patches=None):
        with ExitStack() as stack:
            enter = stack.enter_context
            for name in ('clear_screen', 'pause', 'haptic'):
                if hasattr(module, name):
                    enter(patch.object(module, name))
            if hasattr(module, 'read_command'):
                enter(patch.object(module, 'read_command', side_effect=[*inputs, _Stop()]))
            enter(patch('ui.interface.clear_screen'))
            enter(patch('ui.interface.haptic'))
            enter(patch('builtins.input', return_value=''))
            for target, value in (patches or {}).items():
                enter(patch(target, return_value=value))
            out = enter(redirect_stdout(io.StringIO()))
            call()
        text = out.getvalue()
        self.assertNotRegex(text, LEAK, 'hint list printed raw, use nav_line')
        return text


SCHED = SimpleNamespace(ready=False, weeks=[], start=None, vacations=[], zone='',
                        enabled=False, problems=lambda: [], week_days=lambda: [])
SCHED_PATCHES = {'core.schedule.load': SCHED, 'core.clocks.load': [], 'core.clocks.line': ''}


class Schedule(Screen):
    def test_schedule(self):
        text = self.open(schedule_screen, schedule_screen.schedule_screen, ['b'], SCHED_PATCHES)
        self.assertIn('No schedule yet', text)

    def test_schedule_settings_sections(self):
        self.open(schedule_settings_screen, schedule_settings_screen.schedule_settings,
                  ['1', 'b', '2', 'b', '3', 'b', '4', 'b', 'b'], SCHED_PATCHES)

    def test_zone_frame_hint(self):
        frame = schedule_settings_screen._zone_frame(SCHED, [], '', [], 0, datetime.now(timezone.utc), False)
        self.assertNotRegex(frame, LEAK)
        self.assertIn('back', frame)


SOURCE = SimpleNamespace(NAME='Reminders', TAP='steipete/tap/remindctl', supported=lambda: True,
                         status=lambda: 'denied', terminal=lambda: 'Terminal')


class Settings(Screen):
    def test_sections(self):
        with patch.object(settings_screen, '_SOURCES', [SOURCE]), \
             patch.object(settings_screen, 'schedule_settings') as schedule:
            text = self.open(settings_screen, settings_screen.settings_screen,
                             ['1', 'b', '2', 'b', '3', '4', 'b', 'b'])
        schedule.assert_called_once()
        self.assertIn('no access', text)
        self.assertIn('Settings > Reminders', text)


LISTS = [{'id': 'l1', 'title': 'Home'}]
TASK = {'id': 't1', 'title': 'Buy milk', 'list_name': 'Home', 'due': None,
        'all_day': False, 'notes': '', 'place': ''}
TASKS_PATCHES = {
    'screens.settings_screen.source_setup': True,
    'core.sources.selected': {'l1'},
    'core.sources.default': 'l1',
    'core.tasks.group': [('Home', [TASK])],
    'core.tasks.numbered': [TASK],
    'core.waypoints.load': {},
    'core.editor.available': False,
}


class Tasks(Screen):
    def test_list_card_and_lists(self):
        source = SimpleNamespace(KEY='remindctl', NAME='Reminders', lists=lambda: LISTS, items=lambda: [TASK])
        text = self.open(tasks_screen, lambda: tasks_screen.tasks_screen(source),
                         ['1', 'b', 's', 'b', 'b'], TASKS_PATCHES)
        self.assertIn('Buy milk', text)
        self.assertIn('Settings > Reminders', text)

    def test_stops_when_not_set_up(self):
        source = Mock()
        self.open(tasks_screen, lambda: tasks_screen.tasks_screen(source), [],
                  {'screens.settings_screen.source_setup': False})
        source.lists.assert_not_called()


POINT = {'address': 'Main st 1', 'proximity': 'arriving', 'radius': 100}


class Waypoints(Screen):
    def test_list_and_card(self):
        text = self.open(waypoints_screen, waypoints_screen.waypoints_screen, ['1', 'b', 'b'], {
            'core.waypoints.load': {'home': POINT},
            'core.waypoints.linked': {'home': []},
            'core.sources.remindctl.items': [],
            'core.editor.available': False,
        })
        self.assertIn('@home', text)

    def test_card_hint_without_reminders(self):
        with patch('core.editor.available', return_value=False):
            card = '\n'.join(waypoints_screen._card('home', POINT, [], 1, 1))
        self.assertIn('back', card)

    def test_empty_list_shows_add(self):
        self.assertIn('add', '\n'.join(waypoints_screen._frame({}, {})))


REPORT = {'passed': 3, 'failed': [], 'skipped': 0, 'seconds': 0.1}
DIAG_PATCHES = {
    'core.diagnostics.system_info': ('Holocron', [('Python', '3.15')]),
    'core.archives.load': None,
    'core.keeper.configured': False,
}


class Other(Screen):
    def test_diagnostics(self):
        self.open(diagnostics_screen, diagnostics_screen.diagnostics_screen, ['b'],
                  {**DIAG_PATCHES, 'core.diagnostics.run': REPORT})

    def test_diagnostics_failure_details(self):
        report = {**REPORT, 'failed': [('test_x', 'Traceback\nNameError: x\n')]}
        text = self.open(diagnostics_screen, diagnostics_screen.diagnostics_screen, ['1', 'b'],
                         {**DIAG_PATCHES, 'core.diagnostics.run': report})
        self.assertIn('NameError', text)

    def test_keeper_offline(self):
        text = self.open(keeper_screen, keeper_screen.keeper_screen, ['b'], {
            'core.keeper.configured': False, 'core.keeper.cached': True, 'core.keeper.active': None})
        self.assertIn('No model connected', text)

    def test_favorites_empty(self):
        text = self.open(favorites_screen, favorites_screen.favorites_screen, [],
                         {'core.favorites.resolve': [], 'core.archives.cases': []})
        self.assertIn('No favorites yet', text)

    def test_help(self):
        text = self.open(help_screen, help_screen.show_help, [], {'ui.interface.pause': None})
        self.assertTrue(text.strip())
