import io
import re
import unittest
import os
from unittest import mock
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from ui.interface import visible

from datetime import date
from zoneinfo import ZoneInfo
from unittest.mock import ANY, call
from core import schedule
from screens import (diagnostics_screen, events_screen, favorites_screen, help_screen, keeper_screen,
                     routines_screen, schedule_screen, schedule_settings_screen, settings_screen,
                     sources_screen, tasks_screen, waypoints_screen)

WIDE = os.terminal_size((200, 50))


def setUpModule():
    patch = mock.patch('shutil.get_terminal_size', return_value=WIDE)
    patch.start()
    unittest.addModuleCleanup(patch.stop)

LEAK = re.compile(r"\[\('")


class _Stop(Exception):
    pass


class Screen(unittest.TestCase):
    def open(self, module, call, inputs=(), patches=None):
        feed = iter(inputs)

        def read(*args, **kwargs):
            for value in feed:
                return value
            raise _Stop

        with ExitStack() as stack:
            enter = stack.enter_context
            for target in {module, sources_screen}:
                for name in ('clear_screen', 'pause', 'haptic'):
                    if hasattr(target, name):
                        enter(patch.object(target, name))
                if hasattr(target, 'read_command'):
                    enter(patch.object(target, 'read_command', side_effect=read))
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


SOURCE = SimpleNamespace(NAME='Reminders', SETUP='macos', TAP='steipete/tap/remindctl', PROGRAM='remindctl',
                         MACOS=14, ABOUT='Apple Reminders', PRIVACY='Reminders', supported=lambda: True,
                         status=lambda: 'denied', authorize=lambda: False)


class Settings(Screen):
    def test_sections(self):
        with patch.object(settings_screen.registry, 'ALL', [SOURCE]), \
             patch.object(settings_screen, 'schedule_settings') as schedule, \
             patch.object(settings_screen, 'home_screen') as home, \
             patch.object(settings_screen, 'page_rows', return_value=15):
            text = self.open(settings_screen, settings_screen.settings_screen,
                             ['1', 'b', '2', '3', 'b', '4', 'b', '5', '6', 'b', 'b'])
        home.assert_called_once()
        schedule.assert_called_once()
        self.assertIn('Settings > Lists', text)
        self.assertIn('Rows per page: 15', text)
        self.assertNotIn('no access', text.split('Settings > Reminders')[0])
        self.assertIn('Settings > Reminders', text)

    def test_order(self):
        sources = [SimpleNamespace(NAME=name, supported=lambda: True) for name in ('Calendar', 'Reminders')]
        with patch.object(settings_screen.registry, 'ALL', sources), \
             patch.object(settings_screen, 'show_menu', side_effect=_Stop) as menu:
            with self.assertRaises(_Stop):
                settings_screen.settings_screen()
        self.assertEqual(menu.call_args.args[1],
                         ['User', 'Main screen', 'Lists', 'Archive', 'Schedule', 'Calendar', 'Reminders'])

    def test_unsupported_source_hidden(self):
        sources = [SimpleNamespace(NAME='Calendar', supported=lambda: False),
                   SimpleNamespace(NAME='Reminders', supported=lambda: True)]
        with patch.object(settings_screen.registry, 'ALL', sources), \
             patch.object(settings_screen, 'show_menu', side_effect=_Stop) as menu:
            with self.assertRaises(_Stop):
                settings_screen.settings_screen()
        self.assertEqual(menu.call_args.args[1], ['User', 'Main screen', 'Lists', 'Archive', 'Schedule', 'Reminders'])

    def test_no_main_screen_without_sources(self):
        with patch.object(settings_screen.registry, 'ALL', []), \
             patch.object(settings_screen, 'show_menu', side_effect=_Stop) as menu:
            with self.assertRaises(_Stop):
                settings_screen.settings_screen()
        self.assertEqual(menu.call_args.args[1], ['User', 'Lists', 'Archive', 'Schedule'])


LISTS = [{'id': 'l1', 'title': 'Home'}]
TASK = {'id': 't1', 'title': 'Buy milk', 'list_name': 'Home', 'due': None,
        'all_day': False, 'notes': '', 'place': ''}
TASKS_PATCHES = {
    'screens.tasks_screen.source_setup': True,
    'core.sources.selected': {'l1'},
    'core.sources.default': 'l1',
    'core.tasks.group': [('Home', [TASK])],
    'core.tasks.numbered': [TASK],
    'core.waypoints.load': {},
    'core.editor.available': False,
    'core.sources.option': 0,
    'core.sources.cli.origin': 'holocron',
    'core.sources.cli.which': '/x/remindctl',
    'core.sources.cli.shadowed': None,
}


class Tasks(Screen):
    def test_list_card_and_lists(self):
        source = SimpleNamespace(KEY='remindctl', NAME='Reminders', LISTS='lists', PROGRAM='remindctl',
                                 TAP='steipete/tap/remindctl', lists=lambda: LISTS, items=lambda: [TASK],
                                 SHOWN=3, AHEAD=0, available=lambda: True)
        text = self.open(tasks_screen, lambda: tasks_screen.tasks_screen(source),
                         ['1', 'b', 's', 'b', 'b'], TASKS_PATCHES)
        self.assertIn('Buy milk', text)
        self.assertIn('#Home', text)
        self.assertRegex(text, r'x(#| number)')
        self.assertIn('Settings > Reminders', text)

    def test_stops_when_not_set_up(self):
        source = Mock()
        self.open(tasks_screen, lambda: tasks_screen.tasks_screen(source), [],
                  {'screens.tasks_screen.source_setup': False})
        source.lists.assert_not_called()

    def test_summary_tag(self):
        task = {**TASK, 'list': 'l1', 'done': False}
        source = SimpleNamespace(KEY='remindctl', SHOWN=3, AHEAD=0, available=lambda: True, items=lambda: [task])
        with patch('core.sources.selected', return_value=['l1']), \
             patch('core.sources.option', side_effect=lambda key, name, default: default):
            lines = tasks_screen.summary(source)
        self.assertEqual(visible(lines[0]), '○ Buy milk #Home')

    def test_card_ignores_wrong_number(self):
        found = [{**TASK, 'list': 'l1', 'done': False}, {**TASK, 'id': 't2', 'title': 'Call vendor', 'list': 'l1', 'done': False}]
        with patch.object(tasks_screen, 'clear_screen'), \
             patch.object(tasks_screen, 'read_command', side_effect=['99', '0', '2', 'b']) as read, \
             patch('core.waypoints.load', return_value={}), \
             patch('core.editor.available', return_value=False), \
             redirect_stdout(io.StringIO()) as out:
            tasks_screen._open(SimpleNamespace(), found, 1)
        text = visible(out.getvalue())
        self.assertEqual(read.call_count, 4)
        self.assertEqual(text.count('── 1/2'), 3)
        self.assertEqual(text.count('── 2/2'), 1)
        self.assertIn('Call vendor', text)

    def _add(self, text):
        source = Mock(KEY='remindctl')
        source.add.return_value = True
        with patch.object(tasks_screen, 'error') as error:
            self.open(tasks_screen, lambda: tasks_screen._add(source, text, LISTS, ['l1']), [],
                      {'core.sources.default': 'l1', 'core.waypoints.load': {}})
        return source.add, error

    def test_add_passes_time(self):
        add, error = self._add('Check 22:05 24-12-2030')
        add.assert_called_once_with('Check', 'l1', None, datetime(2030, 12, 24, 22, 5))
        error.assert_not_called()

    def test_add_bad_time_adds_nothing(self):
        add, error = self._add('Check 25:00')
        add.assert_not_called()
        error.assert_called_once_with('No such time: 25:00')


POINT = {'address': 'Main st 1', 'proximity': 'arriving', 'radius': 100}
ROUTINES = [
    {'title': 'Check', 'time': '00:05', 'zone': 'Asia/Dubai', 'rule': 'shift', 'list': 'L1', 'last': None},
    {'title': 'Альфа ok', 'time': '23:59', 'zone': '', 'rule': 'manual', 'list': 'L9', 'last': None},
]
R_LISTS = [{'id': 'L1', 'title': 'Todo'}]
NIGHTS = schedule.Schedule(enabled=True, shifts={'N': [['20:00', '08:00']]}, weeks=('N------',),
                           start=date(2026, 11, 23))
MON = datetime(2026, 11, 23, 12, 0)


class Routines(Screen):
    def _source(self, lists=R_LISTS):
        return SimpleNamespace(KEY='remindctl', lists=lambda: lists)

    def _card(self, routine, sched):
        with patch.object(routines_screen.zones, '_local', return_value=ZoneInfo('Europe/Berlin')), \
             patch('core.editor.available', return_value=False):
            return [visible(l) for l in routines_screen._card(routine, 1, 2, MON, sched, R_LISTS)]

    def test_frame(self):
        lines = [visible(l) for l in routines_screen._frame(ROUTINES)]
        self.assertEqual(lines[:4], ['Routines', '', '  1 Check      00:05 Dubai · on shift',
                                     '  2 Альфа ok   23:59 · by hand'])
        self.assertIn('open', lines[5])

    def test_empty(self):
        lines = [visible(l) for l in routines_screen._frame([])]
        self.assertEqual(lines[2], 'No routines')
        self.assertIn('add', lines[4])
        self.assertNotIn('open', lines[4])

    def test_card_shift_in_team_time(self):
        lines = self._card(ROUTINES[0], NIGHTS)
        self.assertEqual(lines[2:6], ['Check', '00:05 Dubai · 21:05 here', 'on shift · next today 21:05', '#Todo'])
        self.assertIn('remind now', lines[7])
        self.assertNotIn('team / my time', lines[7])
        self.assertNotIn('prev', lines[7])

    def test_card_manual_local(self):
        lines = self._card(ROUTINES[1], NIGHTS)
        self.assertEqual(lines[2:6], ['Альфа ok', '23:59', 'by hand', ''])

    def test_card_without_schedule(self):
        lines = self._card(ROUTINES[0], schedule.Schedule(zone='Asia/Dubai'))
        self.assertEqual(lines[4], 'on shift · schedule not set')
        self.assertIn('team / my time', lines[7])

    def _list(self, inputs, lists=R_LISTS, items=()):
        return self.open(routines_screen, lambda: routines_screen.routines_screen(self._source(lists)), inputs, {
            'screens.routines_screen.source_setup': True,
            'core.routines.load': list(items),
            'core.schedule.load': schedule.Schedule(zone='Asia/Dubai'),
            'core.sources.default': 'L1',
        })

    def test_add(self):
        with patch.object(routines_screen.routines, 'add', return_value=True) as add:
            self._list(['a', 'Check 00:05', 'b'])
        add.assert_called_once_with('Check', '00:05', 'L1', 'Asia/Dubai')

    def test_add_problem_saves_nothing(self):
        with patch.object(routines_screen.routines, 'add') as add, patch.object(routines_screen, 'error') as error:
            self._list(['a', 'Check', 'b'])
        add.assert_not_called()
        error.assert_called_once_with('Type one time, e.g. 00:05')

    def test_wrong_numbers_open_nothing(self):
        with patch.object(routines_screen, '_open') as opened:
            self._list(['²', '0', '3', '', 'b'], items=ROUTINES)
        opened.assert_not_called()

    def test_unreadable_lists(self):
        with patch.object(routines_screen, 'unreadable') as unreadable:
            self._list([], lists=None)
        unreadable.assert_called_once()

    def _keys(self, inputs, confirmed=False):
        source = self._source()
        with patch.object(routines_screen.routines, 'change') as change, \
             patch.object(routines_screen.routines, 'remove') as remove, \
             patch.object(routines_screen.routines, 'remind', return_value=(MON, None)) as remind, \
             patch.object(routines_screen, 'confirm', return_value=confirmed):
            self.open(routines_screen, lambda: routines_screen._open(source, R_LISTS, 1), inputs, {
                'core.routines.load': ROUTINES,
                'core.schedule.load': schedule.Schedule(zone='Asia/Dubai'),
                'core.editor.available': False,
            })
        return source, change, remove, remind

    def test_card_keys(self):
        source, change, remove, remind = self._keys(['t', 'z', 'r', 'd', 'e', 'x', 'b'])
        self.assertEqual(change.call_args_list, [call(1, rule='daily'), call(1, zone='')])
        remind.assert_called_once_with(source, 1, ANY)
        remove.assert_not_called()

    def test_delete(self):
        _, _, remove, _ = self._keys(['d'], confirmed=True)
        remove.assert_called_once_with(1)


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

    def test_keeper_offline_opens_settings(self):
        with patch.object(settings_screen, 'keeper_screen') as settings:
            self.open(keeper_screen, keeper_screen.keeper_screen, [], {
                'core.keeper.configured': False, 'core.keeper.cached': True, 'core.keeper.active': None})
        settings.assert_called_once()

    def test_keeper_opens_after_settings(self):
        conn = {'slot': 'local'}
        with patch.object(settings_screen, 'keeper_screen') as settings, \
                patch.object(keeper_screen, '_wake', side_effect=[None, conn, conn]):
            text = self.open(keeper_screen, keeper_screen.keeper_screen, ['b'], {'core.keeper.has_server': False})
        settings.assert_called_once()
        self.assertIn(keeper_screen.LINES['ready'], visible(text))

    def test_favorites_empty(self):
        text = self.open(favorites_screen, favorites_screen.favorites_screen, [],
                         {'core.favorites.resolve': [], 'core.archives.cases': []})
        self.assertIn('No favorites yet', text)

    def test_help(self):
        text = self.open(help_screen, help_screen.show_help, [], {'ui.interface.pause': None})
        self.assertTrue(text.strip())


CALENDARS = [{'id': 'c1', 'title': 'Work'}]
EVENT = {'id': 'e1', 'title': 'Standup', 'start': datetime(2030, 1, 1, 10), 'end': datetime(2030, 1, 1, 11),
         'all_day': False, 'list': 'c1', 'list_name': 'Work', 'place': '', 'notes': '',
         'url': 'https://meet.google.com/abc'}
EVENTS_PATCHES = {
    'screens.events_screen.source_setup': True,
    'core.sources.selected': ['c1'],
    'core.sources.default': 'c1',
    'core.sources.option': 2,
    'core.sources.cli.origin': 'holocron',
    'core.sources.cli.which': '/x/ekctl',
    'core.sources.cli.shadowed': None,
}


class Calendar(Screen):
    def _source(self, ahead=2):
        return SimpleNamespace(KEY='ekctl', NAME='Calendar', LISTS='calendars', SHOWN=2, AHEAD=ahead,
                               PROGRAM='ekctl', TAP='schappim/ekctl/ekctl', available=lambda: True,
                               lists=lambda: CALENDARS, items=lambda: [EVENT])

    def _agenda(self, now, ahead=2, event=EVENT):
        source = self._source(ahead)
        source.items = lambda: [event]
        with patch('core.sources.selected', return_value=['c1']), \
             patch('core.sources.option', side_effect=lambda key, name, default: default):
            return events_screen.agenda(source, now)

    def _typed(self, source):
        with patch.object(events_screen, '_add') as add:
            self.open(events_screen, lambda: events_screen.events_screen(source),
                      ['a', 'Lunch 12:00', 'b'], EVENTS_PATCHES)
        return add

    def test_list_card_and_calendars(self):
        with patch('core.sources.set_option') as set_option:
            text = self.open(events_screen, lambda: events_screen.events_screen(self._source()),
                             ['1', 'b', 's', 'm 1', 't 3', 'b', 'b'], EVENTS_PATCHES)
        self.assertIn('Standup', text)
        self.assertIn('meet.google.com', text)
        self.assertIn('Settings > Calendar', text)
        self.assertIn('today and tomorrow', text)
        self.assertEqual([c.args for c in set_option.call_args_list],
                         [('ekctl', 'shown', 1), ('ekctl', 'ahead', 3)])

    def test_add_asks_for_text(self):
        source = self._source()
        source.add = lambda *args: True
        add = self._typed(source)
        add.assert_called_once()
        self.assertEqual(add.call_args.args[:2], (source, 'Lunch 12:00'))

    def test_read_only_ignores_add(self):
        self._typed(self._source()).assert_not_called()

    def test_read_only_hides_add(self):
        now = datetime(2030, 1, 1, 9)
        source = self._source()
        frame = '\n'.join(events_screen._frame(source, ['c1'], [], now))
        self.assertNotIn('add', frame)
        self.assertIn('calendars', frame)
        source.add = lambda *args: True
        self.assertIn('add', '\n'.join(events_screen._frame(source, ['c1'], [], now)))

    def test_agenda_shows_link(self):
        lines = self._agenda(datetime(2030, 1, 1, 9))
        self.assertIn('Standup', lines[0])
        self.assertTrue(visible(lines[0]).endswith(' #Work'))
        self.assertEqual(visible(lines[1]).strip(), 'link')
        self.assertIn('https://meet.google.com/abc', lines[1])

    def test_agenda_tomorrow_counts(self):
        self.assertTrue(self._agenda(datetime(2029, 12, 31, 9)))
        self.assertEqual(self._agenda(datetime(2029, 12, 31, 9), ahead=1), [])

    def test_agenda_hides_calendar_page(self):
        event = {**EVENT, 'url': 'https://calendar.yandex.ru/event?event_id=1'}
        self.assertEqual(len(self._agenda(datetime(2030, 1, 1, 9), event=event)), 1)

    def test_card_every_shape(self):
        now = datetime(2030, 1, 1, 9)
        shapes = {
            'link only': EVENT,
            'nothing': {**EVENT, 'url': ''},
            'place only': {**EVENT, 'url': '', 'place': 'Room 1'},
            'place and link': {**EVENT, 'place': 'Room 1'},
            'link is place': {**EVENT, 'url': '', 'place': 'https://zoom.us/j/1'},
        }
        for name, event in shapes.items():
            with self.subTest(name):
                text = '\n'.join(events_screen._card(event, 1, 1, now))
                self.assertIn('Standup', text)

    def test_card_ignores_wrong_number(self):
        events = [EVENT, {**EVENT, 'id': 'e2', 'title': 'Retro'}]
        with patch.object(events_screen, 'clear_screen'), \
             patch.object(events_screen, 'read_command', side_effect=['99', '0', '2', 'b']) as read, \
             redirect_stdout(io.StringIO()) as out:
            events_screen._open(events, 1)
        text = visible(out.getvalue())
        self.assertEqual(read.call_count, 4)
        self.assertEqual(text.count('── 1/2'), 3)
        self.assertEqual(text.count('── 2/2'), 1)
        self.assertIn('Retro', text)
