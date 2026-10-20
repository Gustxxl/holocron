import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import settings
from screens import settings_screen as screen
from tests.test_config import Base


class Reorder(unittest.TestCase):
    ITEMS = ['a', 'b', 'c']

    def test_full(self):
        self.assertEqual(settings.reorder(self.ITEMS, '312'), ['c', 'a', 'b'])

    def test_one_goes_first(self):
        self.assertEqual(settings.reorder(self.ITEMS, '3'), ['c', 'a', 'b'])

    def test_rest_keep_order(self):
        self.assertEqual(settings.reorder(self.ITEMS, '2'), ['b', 'a', 'c'])

    def test_spaces(self):
        self.assertEqual(settings.reorder(self.ITEMS, '2 1'), ['b', 'a', 'c'])

    def test_bad_input(self):
        for text in ('', ' ', '0', '4', '11', 'x', '1,2', '-1'):
            with self.subTest(text):
                self.assertIsNone(settings.reorder(self.ITEMS, text))


class HomeOrder(Base):
    def test_default(self):
        self.assertEqual(settings.home_order(), list(settings.HOME_BLOCKS))

    def test_saved(self):
        settings.update_home_order(['reminders', 'calendar', 'schedule'])
        self.assertEqual(settings.home_order(), ['reminders', 'calendar', 'schedule'])

    def test_missing_go_last(self):
        self.write(json.dumps({'home_order': ['reminders']}))
        self.assertEqual(settings.home_order(), ['reminders', 'calendar', 'schedule'])

    def test_unknown_and_repeats_dropped(self):
        self.write(json.dumps({'home_order': ['weather', 'reminders', 'reminders', 5, ['x']]}))
        self.assertEqual(settings.home_order(), ['reminders', 'calendar', 'schedule'])

    def test_not_a_list(self):
        self.write(json.dumps({'home_order': 'reminders'}))
        self.assertEqual(settings.home_order(), list(settings.HOME_BLOCKS))

    def test_reset(self):
        settings.update_home_order(['reminders', 'calendar', 'schedule'])
        settings.update_home_order([])
        self.assertEqual(settings.home_order(), list(settings.HOME_BLOCKS))


class Screen(unittest.TestCase):
    NAMES = {'calendar': 'Calendar', 'reminders': 'Reminders'}
    BLOCKS = ('Calendar', 'Schedule', 'Reminders')

    def _run(self, *inputs, names=None):
        names = self.NAMES if names is None else names

        def block(key):
            return SimpleNamespace(NAME=names[key]) if key in names else None

        with patch.object(screen, 'home_order', return_value=['calendar', 'schedule', 'reminders']), \
             patch.object(screen, 'update_home_order') as update, \
             patch.object(screen.registry, 'block', side_effect=block), \
             patch.object(screen, 'clear_screen'), \
             patch('builtins.print') as out, \
             patch.object(screen, 'error') as error, \
             patch.object(screen, 'read_command', side_effect=[*inputs, 'b']):
            screen.home_screen()
        self.printed = [str(c.args[0]) for c in out.call_args_list if c.args]
        return update, error

    def _rows(self):
        return [name for line in self.printed for name in self.BLOCKS if line.endswith(name)]

    def test_names_from_sources(self):
        self._run()
        self.assertEqual(self._rows(), ['Calendar', 'Schedule', 'Reminders'])

    def test_unsupported_block_hidden(self):
        self._run(names={'reminders': 'Reminders'})
        self.assertEqual(self._rows(), ['Schedule', 'Reminders'])

    def test_hidden_block_keeps_place(self):
        update, _ = self._run('2', names={'reminders': 'Reminders'})
        update.assert_called_once_with(['reminders', 'schedule', 'calendar'])

    def test_move_first(self):
        update, _ = self._run('3')
        update.assert_called_once_with(['reminders', 'calendar', 'schedule'])

    def test_full_order(self):
        update, _ = self._run('231')
        update.assert_called_once_with(['schedule', 'reminders', 'calendar'])

    def test_default(self):
        update, _ = self._run('d')
        update.assert_called_once_with([])

    def test_bad_input(self):
        update, error = self._run('9')
        update.assert_not_called()
        error.assert_called_once_with('Type block numbers, e.g. 31')

    def test_bad_input_counts_shown_blocks(self):
        _, error = self._run('9', names={'reminders': 'Reminders'})
        error.assert_called_once_with('Type block numbers, e.g. 21')

    def test_empty_input(self):
        update, error = self._run('')
        update.assert_not_called()
        error.assert_not_called()

    def test_back(self):
        update, _ = self._run()
        update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
