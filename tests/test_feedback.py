import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from screens import main_screen, schedule_settings_screen, search_screen, settings_screen
from ui import interface


class Pause(unittest.TestCase):
    def pause(self, **kwargs):
        calls = mock.Mock()
        with mock.patch.object(interface, 'haptic', calls.haptic), \
             mock.patch('builtins.input', calls.input), \
             mock.patch('builtins.print'):
            interface.pause(**kwargs)
        return calls

    def test_silent_by_default(self):
        calls = self.pause()
        calls.haptic.assert_not_called()
        calls.input.assert_called_once()

    def test_feedback_before_enter(self):
        calls = self.pause(feedback='success')
        self.assertEqual([name for name, *_ in calls.mock_calls], ['haptic', 'input'])
        calls.haptic.assert_called_once_with('success')

    def test_error_once(self):
        with mock.patch.object(interface, 'clear_screen'), \
             mock.patch.object(interface, 'haptic') as haptic, \
             mock.patch('builtins.input'), mock.patch('builtins.print'):
            interface.error('Alpha')
        haptic.assert_called_once_with('error')


class Settings(unittest.TestCase):
    def run_screen(self, screen, commands, **values):
        with ExitStack() as stack:
            for name, value in values.items():
                stack.enter_context(mock.patch.object(settings_screen, name, return_value=value))
            stack.enter_context(mock.patch.object(settings_screen, 'clear_screen'))
            stack.enter_context(mock.patch.object(settings_screen.archives, 'load'))
            stack.enter_context(mock.patch('builtins.print'))
            pause = stack.enter_context(mock.patch.object(settings_screen, 'pause'))
            error = stack.enter_context(mock.patch.object(settings_screen, 'error'))
            haptic = stack.enter_context(mock.patch.object(settings_screen, 'haptic'))
            stack.enter_context(mock.patch.object(settings_screen, 'read_command', side_effect=[*commands, 'b']))
            screen()
        return haptic, error, pause

    def test_rows(self):
        haptic, error, _ = self.run_screen(settings_screen.rows_screen, ['20', 'd', '500'],
                                           page_rows=15, update_page_rows=None)
        self.assertEqual(haptic.call_args_list, [mock.call('toggle')] * 2)
        error.assert_called_once()

    def test_separator(self):
        haptic, error, _ = self.run_screen(settings_screen.separator_screen, [';', 'd', 'c', 'abc'],
                                           search_separator='', update_search_separator=None)
        self.assertEqual(haptic.call_args_list, [mock.call('toggle')] * 3)
        error.assert_called_once()

    def test_name(self):
        haptic, _, _ = self.run_screen(settings_screen.user_screen, ['Alpha', 'c'],
                                       operator_name='', update_operator_name=None)
        self.assertEqual(haptic.call_args_list, [mock.call('toggle')] * 2)

    def test_path_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp, 'Alpha.md')
            board.write_text('Alpha', encoding='utf-8')
            _, _, pause = self.run_screen(settings_screen.excalidraw_obsidian_screen, [str(board)],
                                          archive_path='', update_archive_path=None)
        pause.assert_called_once_with(feedback='success')

    def test_server_address(self):
        for answer, update, count in (('alpha', None, 1), ('alpha beta', ValueError('alpha beta'), 0)):
            with self.subTest(answer=answer), \
                 mock.patch.object(settings_screen.keeper, 'connection', return_value=None), \
                 mock.patch.object(settings_screen.keeper, 'reset'), \
                 mock.patch.object(settings_screen, 'update_keeper_server', side_effect=update):
                haptic, _, _ = self.run_screen(settings_screen._server_screen, [answer])
            self.assertEqual(haptic.call_count, count)


class Schedule(unittest.TestCase):
    def test_toggle(self):
        for enabled in (True, False):
            sched = SimpleNamespace(enabled=enabled, problems=lambda: [])
            with self.subTest(enabled=enabled), \
                 mock.patch.object(schedule_settings_screen.schedule, 'set_enabled') as switch, \
                 mock.patch.object(schedule_settings_screen, 'haptic') as haptic:
                schedule_settings_screen._toggle(sched)
            switch.assert_called_once_with(not enabled)
            haptic.assert_called_once_with('toggle')

    def test_toggle_blocked(self):
        sched = SimpleNamespace(enabled=False, problems=lambda: ['no weeks'])
        with mock.patch.object(schedule_settings_screen.schedule, 'set_enabled') as switch, \
             mock.patch.object(schedule_settings_screen, 'error') as error, \
             mock.patch.object(schedule_settings_screen, 'haptic') as haptic:
            schedule_settings_screen._toggle(sched)
        switch.assert_not_called()
        haptic.assert_not_called()
        error.assert_called_once()

    def test_vacation_added(self):
        with mock.patch.object(schedule_settings_screen, 'read_command', side_effect=['01-11-2026', '']), \
             mock.patch.object(schedule_settings_screen.schedule, 'save_vacations') as save, \
             mock.patch.object(schedule_settings_screen, 'haptic') as haptic, \
             mock.patch('builtins.print'):
            schedule_settings_screen._add_vacation([])
        save.assert_called_once()
        haptic.assert_called_once_with('success')

    def zone(self, removed):
        with mock.patch.object(schedule_settings_screen, '_zone_frame', return_value=''), \
             mock.patch.object(schedule_settings_screen.schedule, 'load'), \
             mock.patch.object(schedule_settings_screen.clocks, 'load', return_value=[]), \
             mock.patch.object(schedule_settings_screen.clocks, 'remove', return_value=removed), \
             mock.patch.object(schedule_settings_screen, 'clear_screen'), \
             mock.patch.object(schedule_settings_screen, 'haptic') as haptic, \
             mock.patch.object(schedule_settings_screen, 'read_command', side_effect=['d 5', 'b']), \
             mock.patch('builtins.print'):
            schedule_settings_screen._zone_screen()
        return haptic

    def test_clock_removed(self):
        self.zone(True).assert_called_once_with('toggle')

    def test_missing_clock_silent(self):
        self.zone(False).assert_not_called()


class Search(unittest.TestCase):
    def open(self, query, cases, **patches):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(search_screen.archives, 'cases', return_value=cases))
            stack.enter_context(mock.patch.object(search_screen.archives, 'missing', return_value=[]))
            stack.enter_context(mock.patch.object(search_screen, 'search_separator', return_value=';'))
            stack.enter_context(mock.patch.object(search_screen, 'clear_screen'))
            stack.enter_context(mock.patch.object(search_screen, 'read_command', side_effect=['b']))
            stack.enter_context(mock.patch('builtins.print'))
            for name, value in patches.items():
                stack.enter_context(mock.patch.object(search_screen, name, return_value=value))
            pause = stack.enter_context(mock.patch.object(search_screen, 'pause'))
            haptic = stack.enter_context(mock.patch.object(search_screen, 'haptic'))
            search_screen.search_screen(query)
        return pause, haptic

    def test_short_query_warns(self):
        pause, _ = self.open('ab', [{'text': 'Alpha'}])
        pause.assert_called_once_with(feedback='warning')

    def test_no_archive_warns(self):
        pause, _ = self.open('Alpha', [])
        pause.assert_called_once_with(feedback='warning')

    def test_nothing_found_warns(self):
        _, haptic = self.open('Gamma', [{'text': 'Alpha'}], _too_short=False,
                              _run=([], None, 'Gamma', False), _suggest=[])
        haptic.assert_called_once_with('warning')


class Main(unittest.TestCase):
    def test_no_archive_warns(self):
        with mock.patch.object(main_screen, 'lookup', return_value=None), \
             mock.patch.object(main_screen.archives, 'is_loaded', return_value=False), \
             mock.patch.object(main_screen.archives, 'missing', return_value=[]), \
             mock.patch.object(main_screen, 'pause') as pause, \
             mock.patch('builtins.print'):
            main_screen._handle('Alpha')
        pause.assert_called_once_with(feedback='warning')


if __name__ == '__main__':
    unittest.main()
