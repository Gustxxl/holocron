import unittest
from unittest import mock

from screens import search_screen

CASE = {'text': 'Alpha record'}


class Back(unittest.TestCase):
    def run_screen(self, query, commands, opened):
        with mock.patch.object(search_screen.archives, 'cases', return_value=[CASE]), \
             mock.patch.object(search_screen.archives, 'load'), \
             mock.patch.object(search_screen, '_find', return_value=([(0, CASE)], None)), \
             mock.patch.object(search_screen, 'search_separator', return_value=';'), \
             mock.patch.object(search_screen, '_exact', return_value=None), \
             mock.patch.object(search_screen, 'clear_screen'), mock.patch('builtins.print'), \
             mock.patch.object(search_screen, 'show_list', side_effect=lambda r, page, *a, **k: page) as shown, \
             mock.patch.object(search_screen, 'open_case', side_effect=opened), \
             mock.patch.object(search_screen, 'read_command', side_effect=commands):
            search_screen.search_screen(query)
        return [(c.args[2], c.args[1]) for c in shown.call_args_list]

    def test_back_leaves(self):
        self.assertEqual(self.run_screen('alpha', ['b'], []), [('alpha', 0)])

    def test_query_from_case_runs(self):
        shown = self.run_screen('alpha', ['n', '1', 'b'], ['gamma'])
        self.assertEqual(shown, [('alpha', 0), ('alpha', 1), ('gamma', 0)])

    def test_l_is_too_short(self):
        with mock.patch.object(search_screen, 'pause') as pause:
            self.assertEqual(self.run_screen('alpha', ['l', 'b'], []), [('alpha', 0), ('alpha', 0)])
        pause.assert_called_once_with(feedback='warning')


class CaseTree(unittest.TestCase):
    def test_l_opens_tree(self):
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen, 'read_command', side_effect=['l', 'b']), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch('screens.tree_screen.tree_screen') as tree:
            self.assertIsNone(search_screen.open_case([(0, CASE)], 1, 'alpha'))
        tree.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
