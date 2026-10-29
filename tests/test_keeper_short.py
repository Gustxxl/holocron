import unittest
from unittest import mock
import io

from ui.interface import dim, num
from screens import keeper_screen, search_screen

CONN = {'slot': 'local'}


def _printed(printed):
    return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)


class Short(unittest.TestCase):
    def run_screen(self, command, conn=CONN):
        state = dict(keeper_screen._short(command), kind='reply', via='local')
        with mock.patch.object(keeper_screen, '_SESSION', {'turns': [], 'records': []}), \
             mock.patch.object(keeper_screen, '_redraw', return_value=('local', 0)), \
             mock.patch.object(keeper_screen, '_drop_nav'), mock.patch.object(keeper_screen, '_nav'), \
             mock.patch.object(keeper_screen, '_width', return_value=200), \
             mock.patch.object(keeper_screen, 'Spinner'), \
             mock.patch.object(keeper_screen, 'haptic') as haptic, \
             mock.patch.object(keeper_screen, '_ask', return_value=state) as ask, \
             mock.patch.object(keeper_screen.keeper, 'active', return_value=conn), \
             mock.patch.object(keeper_screen, 'read_command', side_effect=[command, 'b']), \
             mock.patch('builtins.print') as printed:
            keeper_screen.keeper_screen()
        return ask, haptic, _printed(printed)

    def test_short_cut_with_model(self):
        ask, haptic, out = self.run_screen('ab')
        ask.assert_not_called()
        self.assertIn('Type at least 3 characters.', out)
        haptic.assert_called_once_with('warning')

    def test_short_cut_without_model(self):
        ask, _, out = self.run_screen('ab', conn=None)
        ask.assert_not_called()
        self.assertIn('Type at least 3 characters.', out)

    def test_spaces_do_not_count(self):
        ask, _, _ = self.run_screen('  ab  ')
        ask.assert_not_called()

    def test_bound_is_asked(self):
        ask, _, out = self.run_screen('abc')
        ask.assert_called_once()
        self.assertNotIn('Type at least', out)

    def test_cyrillic(self):
        self.run_screen('аб')[0].assert_not_called()
        self.run_screen('абв')[0].assert_called_once()

    def test_same_bound_as_search(self):
        self.assertEqual(keeper_screen.LINES['short'], f'Type at least {search_screen.MIN_QUERY} characters.')
        with mock.patch.object(keeper_screen, 'MIN_QUERY', 5):
            self.run_screen('abcd')[0].assert_not_called()


class Header(unittest.TestCase):
    def draw(self, focus):
        out = io.StringIO()
        with mock.patch.object(keeper_screen, '_width', return_value=200), \
             mock.patch.object(keeper_screen, '_nav'), \
             mock.patch.object(keeper_screen.keeper, 'has_server', return_value=False), \
             mock.patch('sys.stdout', out):
            keeper_screen._draw([], [], focus, None, CONN)
        return out.getvalue()

    def test_blank_line_under_title_with_record(self):
        out = self.draw({'text': 'Alpha record'})
        self.assertTrue(out.startswith(f"{dim('Keeper')}\n\n{num(1)}{dim('Alpha record')}\n\n"))

    def test_blank_line_under_title_without_record(self):
        self.assertTrue(self.draw(None).startswith(f"{dim('Keeper')}\n\n  Awaiting"))
