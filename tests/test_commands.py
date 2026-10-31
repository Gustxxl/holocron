import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import commands


class Lookup(unittest.TestCase):
    def test_alias_and_case(self):
        self.assertEqual(commands.lookup(' S ').name, 'settings')

    def test_unknown(self):
        self.assertIsNone(commands.lookup('nginx'))


class Note(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def _found(self, folder, has_editor=True):
        with patch.object(commands, 'new_cases_path', return_value=folder), \
             patch.object(commands.editor, 'available', return_value=has_editor):
            return commands.lookup('note') is not None

    def test_available_with_folder_and_editor(self):
        self.assertTrue(self._found(self.dir))

    def test_hidden_without_folder(self):
        self.assertFalse(self._found(''))

    def test_hidden_when_folder_missing(self):
        self.assertFalse(self._found(self.dir + '/nope'))

    def test_hidden_without_editor(self):
        self.assertFalse(self._found(self.dir, has_editor=False))


class Hyperspace(unittest.TestCase):
    def test_hidden_without_curses(self):
        with patch.object(commands, 'HAS_CURSES', False):
            self.assertIsNone(commands.lookup('hy'))
            self.assertIsNone(commands.lookup('hyperspace'))

    def test_available_with_curses(self):
        with patch.object(commands, 'HAS_CURSES', True):
            self.assertEqual(commands.lookup('hy').name, 'hyperspace')


def _entry(section, name):
    return next(e for title, entries in commands.HELP_SECTIONS if title == section for e in entries if e.name == name)


class Keeper(unittest.TestCase):
    CONN = {'slot': 'local', 'url': 'http://l', 'model': 'm'}

    def _configured(self, conns):
        return patch.object(commands.keeper, 'configured', return_value=conns)

    def test_available_with_model(self):
        with self._configured([self.CONN]), patch.object(commands.keeper, 'active') as active:
            for name in ('k', 'K', 'keep', 'keeper'):
                with self.subTest(name):
                    self.assertEqual(commands.lookup(name).name, 'keeper')
        active.assert_not_called()

    def test_hidden_without_model(self):
        with self._configured([]), patch.object(commands.keeper, 'active') as active:
            for name in ('k', 'keep', 'keeper'):
                with self.subTest(name):
                    self.assertIsNone(commands.lookup(name))
        active.assert_not_called()

    def test_help_follows_model(self):
        for conns, shown in (([self.CONN], True), ([], False)):
            with self.subTest(shown), self._configured(conns):
                self.assertIs(_entry('Commands', 'keeper / k').when(), shown)
                self.assertIs(_entry('Search', 'k').when(), shown)

    def test_opens_keeper(self):
        with self._configured([self.CONN]), patch('screens.keeper_screen.keeper_screen') as screen:
            commands.lookup('k').run('k')
        screen.assert_called_once_with()


class Sources(unittest.TestCase):
    def _source(self, ready=True, add=True):
        source = SimpleNamespace(available=lambda: ready)
        if add:
            source.add = lambda *args: True
        return source

    def _active(self, events=None, tasks=None):
        return patch.object(commands.registry, 'active', side_effect={'events': events, 'tasks': tasks}.get)

    def test_calendar_with_source(self):
        with self._active(events=self._source()):
            self.assertEqual(commands.lookup('c').name, 'calendar')
            self.assertEqual(commands.lookup('cal').name, 'calendar')

    def test_calendar_hidden_without_source(self):
        with self._active(tasks=self._source()):
            self.assertIsNone(commands.lookup('c'))

    def test_calendar_hidden_when_not_ready(self):
        with self._active(events=self._source(ready=False)):
            self.assertIsNone(commands.lookup('calendar'))

    def test_reminders_with_source(self):
        with self._active(tasks=self._source()):
            self.assertEqual(commands.lookup('r').name, 'reminders')

    def test_reminders_hidden_when_not_ready(self):
        with self._active(events=self._source(), tasks=self._source(ready=False)):
            self.assertIsNone(commands.lookup('reminders'))

    def test_calendar_opens_active_source(self):
        source = self._source()
        with self._active(events=source), patch('screens.events_screen.events_screen') as screen:
            commands.lookup('c').run('c')
        screen.assert_called_once_with(source)

    def test_reminders_open_active_source(self):
        source = self._source()
        with self._active(tasks=source), patch('screens.tasks_screen.tasks_screen') as screen:
            commands.lookup('r').run('r')
        screen.assert_called_once_with(source)

    def test_read_only_calendar_hides_add_help(self):
        with self._active(events=self._source(add=False)):
            self.assertTrue(_entry('Calendar', '[number]').when())
            self.assertFalse(_entry('Calendar', 'a').when())
        with self._active(events=self._source()):
            self.assertTrue(_entry('Calendar', 'a').when())

    def test_calendar_help_hidden_without_source(self):
        with self._active():
            self.assertFalse(_entry('Calendar', '[number]').when())
            self.assertFalse(_entry('Calendar', 'a').when())

    def test_reminder_help_follows_source(self):
        for ready in (True, False):
            with self.subTest(ready), self._active(tasks=self._source(ready=ready)):
                for name in ('[number]', 'x number', 'a'):
                    self.assertEqual(_entry('Reminders', name).when(), ready)

    def test_edit_reminder_needs_editor(self):
        for has_editor in (True, False):
            with self.subTest(has_editor), self._active(tasks=self._source()), \
                 patch.object(commands.editor, 'available', return_value=has_editor):
                self.assertEqual(_entry('Reminders', 'e').when(), has_editor)

    def test_waypoints_stay_with_apple_reminders(self):
        with self._active(tasks=self._source()), patch.object(commands.remindctl.system, 'IS_MACOS', False):
            self.assertIsNone(commands.lookup('wp'))
