import json
import unittest
from unittest.mock import patch

from core import settings
from screens import settings_screen as screen
from tests.test_config import Base


class PageRows(Base):
    def test_default(self):
        self.assertEqual(settings.page_rows(), 15)

    def test_saved(self):
        settings.update_page_rows(30)
        self.assertEqual(settings.page_rows(), 30)

    def test_bounds(self):
        for rows in (5, 99):
            with self.subTest(rows):
                self.write(json.dumps({'page_rows': rows}))
                self.assertEqual(settings.page_rows(), rows)

    def test_out_of_range_or_garbage(self):
        for value in (4, 100, 0, -1, '20', 20.0, True, None, [20]):
            with self.subTest(value):
                self.write(json.dumps({'page_rows': value}))
                self.assertEqual(settings.page_rows(), 15)


class Screen(unittest.TestCase):
    def _run(self, *inputs, rows=15):
        with patch.object(screen, 'page_rows', return_value=rows), \
             patch.object(screen, 'update_page_rows') as update, \
             patch.object(screen, 'clear_screen'), \
             patch('builtins.print') as out, \
             patch.object(screen, 'error') as error, \
             patch.object(screen, 'read_command', side_effect=[*inputs, 'b']):
            screen.rows_screen()
        self.printed = [str(c.args[0]) for c in out.call_args_list if c.args]
        return update, error

    def test_shows_current(self):
        self._run(rows=30)
        self.assertIn('Rows per page: 30', self.printed)

    def test_set(self):
        update, error = self._run('40')
        update.assert_called_once_with(40)
        error.assert_not_called()

    def test_bounds(self):
        for text, rows in (('5', 5), ('99', 99)):
            with self.subTest(text):
                update, _ = self._run(text)
                update.assert_called_once_with(rows)

    def test_default(self):
        update, _ = self._run('d')
        update.assert_called_once_with(15)

    def test_bad_input(self):
        for text in ('4', '100', '0', 'x', '²', '2 0', '-5', '1.5'):
            with self.subTest(text):
                update, error = self._run(text)
                update.assert_not_called()
                error.assert_called_once_with('Type a number from 5 to 99')

    def test_empty_input(self):
        update, error = self._run('')
        update.assert_not_called()
        error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
