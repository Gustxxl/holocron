import unittest
from unittest import mock

from screens import settings_screen as screen

CONN = {'slot': 'server', 'url': 'http://x', 'model': 'beta:7b'}


class Models(unittest.TestCase):
    def run_screen(self, state, found, commands, conn=CONN):
        with mock.patch.object(screen.keeper, 'connection', return_value=conn), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen, 'wait', return_value=(state, found)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, 'update_keeper_model') as update, \
             mock.patch.object(screen, 'read_command', side_effect=commands), \
             mock.patch('builtins.print') as printed:
            screen._keeper_models_screen(conn['slot'])
        out = '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)
        return out, update

    def test_lists_models(self):
        out, _ = self.run_screen('ready', ['alpha:1b', 'beta:7b'], ['b'])
        lines = out.splitlines()
        self.assertTrue(any('1' in ln and 'alpha:1b' in ln for ln in lines))
        self.assertTrue(any('2' in ln and 'beta:7b' in ln for ln in lines))
        self.assertLess(out.index('alpha:1b'), out.index('beta:7b'))
        self.assertLess(out.index('beta:7b'), out.index('[number] select'))

    def test_current_marked_once(self):
        out, _ = self.run_screen('ready', ['alpha:1b', 'beta:7b'], ['b'])
        marked = [ln for ln in out.splitlines() if 'current' in ln]
        self.assertEqual(len(marked), 1)
        self.assertIn('beta:7b', marked[0])

    def test_no_current(self):
        out, _ = self.run_screen('no_model', ['alpha:1b'], ['b'], conn=dict(CONN, model=''))
        self.assertIn('alpha:1b', out)
        self.assertNotIn('current', out)

    def test_select_by_number(self):
        _, update = self.run_screen('ready', ['alpha:1b', 'beta:7b'], ['1'])
        update.assert_called_once_with('server', 'alpha:1b')

    def test_bad_number_ignored(self):
        _, update = self.run_screen('ready', ['alpha:1b'], ['0', '2', 'x', 'b'])
        update.assert_not_called()

    def test_wide_list_aligned(self):
        found = [f'model-{n}:1b' for n in range(1, 12)]
        out, update = self.run_screen('ready', found, ['11'])
        rows = [ln for ln in out.splitlines() if 'model-' in ln]
        self.assertEqual(len(rows), 11)
        self.assertEqual(len({ln.index('model-') for ln in rows}), 1)
        update.assert_called_once_with('server', 'model-11:1b')

    def test_nothing_found(self):
        out, update = self.run_screen('off', [], ['b'])
        self.assertIn('is not responding', out)
        self.assertNotIn('[number] select', out)
        update.assert_not_called()

    def test_cyrillic_name(self):
        out, _ = self.run_screen('ready', ['модель:1b'], ['b'])
        self.assertIn('модель:1b', out)


if __name__ == '__main__':
    unittest.main()
