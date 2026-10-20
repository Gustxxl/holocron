import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from screens import main_screen as main
from ui.interface import visible


class _Stop(Exception):
    pass


def _source(key):
    return SimpleNamespace(KIND=main.registry.BLOCKS[key])


class Dispatch(unittest.TestCase):
    def _run(self, *inputs, loaded=True):
        with patch.object(main, '_frame', return_value=[]), \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main, 'pause'), \
             patch.object(main.archives, 'is_loaded', return_value=loaded), \
             patch.object(main.archives, 'missing', return_value=[]), \
             patch.object(main, 'read_command', side_effect=[*inputs, _Stop()]), \
             patch.object(main, 'search_screen') as search, \
             patch('core.commands.settings_screen') as settings:
            with self.assertRaises(_Stop):
                main.main_screen()
        return search, settings

    def test_query_goes_to_search(self):
        search, settings = self._run('nginx')
        search.assert_called_once_with('nginx')
        settings.assert_not_called()

    def test_command_runs_without_search(self):
        search, settings = self._run('s')
        settings.assert_called_once()
        search.assert_not_called()

    def test_empty_input_only_redraws(self):
        search, settings = self._run('')
        search.assert_not_called()
        settings.assert_not_called()

    def test_no_archive_no_search(self):
        search, _ = self._run('nginx', loaded=False)
        search.assert_not_called()

    def test_several_inputs_in_a_row(self):
        search, settings = self._run('s', 'nginx', '', 'redis')
        self.assertEqual([c.args for c in search.call_args_list], [('nginx',), ('redis',)])
        settings.assert_called_once()

    def test_back_does_nothing(self):
        search, settings = self._run('b', 'back', 'B')
        search.assert_not_called()
        settings.assert_not_called()

    def test_home_from_inner_screen(self):
        with patch.object(main, '_frame', return_value=[]), \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main.archives, 'is_loaded', return_value=True), \
             patch.object(main, 'read_command', side_effect=['nginx', 'redis', _Stop()]), \
             patch.object(main, 'search_screen', side_effect=[main.Home(), None]) as search:
            with self.assertRaises(_Stop):
                main.main_screen()
        self.assertEqual([c.args for c in search.call_args_list], [('nginx',), ('redis',)])

    def test_home_on_main_redraws(self):
        with patch.object(main, '_frame', return_value=[]) as frame, \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main, 'read_command', side_effect=[main.Home(), _Stop()]):
            with self.assertRaises(_Stop):
                main.main_screen()
        self.assertEqual(frame.call_count, 2)


class Frame(unittest.TestCase):
    def test_frame_ready_before_clear(self):
        calls = []
        with patch.object(main, '_frame', side_effect=lambda: calls.append('frame') or []), \
             patch.object(main, 'clear_screen', side_effect=lambda: calls.append('clear')), \
             patch('builtins.print'), \
             patch.object(main, 'read_command', side_effect=_Stop()):
            with self.assertRaises(_Stop):
                main.main_screen()
        self.assertEqual(calls, ['frame', 'clear'])


class Width(unittest.TestCase):
    def test_lines_fit_terminal(self):
        long = 'x' * 100
        with patch.object(main, '_logo', return_value=[]), \
             patch.object(main, 'operator_name', return_value=long), \
             patch.object(main.archives, 'count', return_value=0), \
             patch.object(main, 'duty_line', return_value=long), \
             patch.object(main.registry, 'block', side_effect=_source), \
             patch.object(main, 'agenda', return_value=[long]), \
             patch.object(main, 'summary', return_value=[long]), \
             patch.object(main, 'pending_update', return_value=False), \
             patch('shutil.get_terminal_size', return_value=os.terminal_size((30, 24))):
            lines = main._frame()
        self.assertTrue(lines)
        self.assertTrue(all(len(visible(line)) <= 29 for line in lines))


class Blocks(unittest.TestCase):
    def _frame(self, order, duty='● ON DUTY'):
        with patch.object(main, '_logo', return_value=[]), \
             patch.object(main, 'operator_name', return_value=''), \
             patch.object(main.archives, 'count', return_value=0), \
             patch.object(main, 'pending_update', return_value=False), \
             patch.object(main, 'home_order', return_value=order), \
             patch.object(main.registry, 'block', side_effect=_source), \
             patch.object(main, 'agenda', return_value=['◇ Standup']), \
             patch.object(main, 'duty_line', return_value=duty), \
             patch.object(main, 'summary', return_value=['○ Buy milk']):
            return main._frame()[1:]

    def test_default_order(self):
        lines = self._frame(['calendar', 'schedule', 'reminders'])
        self.assertEqual([l for l in lines if l], ['◇ Standup', '● ON DUTY', '○ Buy milk'])

    def test_custom_order(self):
        lines = self._frame(['schedule', 'reminders', 'calendar'])
        self.assertEqual([l for l in lines if l], ['● ON DUTY', '○ Buy milk', '◇ Standup'])

    def test_empty_block_no_gap(self):
        lines = self._frame(['calendar', 'schedule', 'reminders'], duty='')
        self.assertEqual(lines, ['', '◇ Standup', '', '○ Buy milk', ''])


class Route(unittest.TestCase):
    def _block(self, key, source=None):
        with patch.object(main.registry, 'block', return_value=source) as self.found, \
             patch.object(main, 'agenda', return_value=['event']) as self.agenda, \
             patch.object(main, 'summary', return_value=['task']) as self.summary, \
             patch.object(main, 'duty_line', return_value=self.duty):
            return main._block(key)

    def setUp(self):
        self.duty = '● ON DUTY'

    def test_calendar_shows_agenda(self):
        source = _source('calendar')
        self.assertEqual(self._block('calendar', source), ['event'])
        self.found.assert_called_once_with('calendar')
        self.agenda.assert_called_once_with(source)
        self.summary.assert_not_called()

    def test_reminders_show_summary(self):
        source = _source('reminders')
        self.assertEqual(self._block('reminders', source), ['task'])
        self.summary.assert_called_once_with(source)
        self.agenda.assert_not_called()

    def test_kind_picks_view(self):
        self.assertEqual(self._block('calendar', SimpleNamespace(KIND='tasks')), ['task'])

    def test_no_source_no_block(self):
        self.assertEqual(self._block('calendar'), [])
        self.agenda.assert_not_called()
        self.summary.assert_not_called()

    def test_schedule_skips_sources(self):
        self.assertEqual(self._block('schedule'), ['● ON DUTY'])
        self.found.assert_not_called()

    def test_empty_schedule(self):
        self.duty = ''
        self.assertEqual(self._block('schedule'), [])
