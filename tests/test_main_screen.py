import unittest
from unittest.mock import patch

from screens import main_screen as main


class _Stop(Exception):
    pass


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
