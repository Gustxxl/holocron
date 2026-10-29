import unittest
from unittest import mock

from screens import search_screen

CASE = {'text': 'Alpha record'}


class Back(unittest.TestCase):
    def run_screen(self, query, commands, opened):
        with mock.patch.object(search_screen.archives, 'cases', return_value=[CASE]), \
             mock.patch.object(search_screen.archives, 'load'), \
             mock.patch.object(search_screen, '_find', return_value=([(0, CASE)], None)), \
             mock.patch.object(search_screen.favorites, 'resolve', return_value=[]), \
             mock.patch.object(search_screen, 'search_separator', return_value=';'), \
             mock.patch.object(search_screen, 'page_rows', return_value=15), \
             mock.patch.object(search_screen, '_exact', return_value=None), \
             mock.patch.object(search_screen, 'clear_screen'), mock.patch('builtins.print'), \
             mock.patch.object(search_screen, 'show_list', side_effect=lambda r, page, *a, **k: page) as shown, \
             mock.patch.object(search_screen, 'open_case', side_effect=opened), \
             mock.patch.object(search_screen, 'read_command', side_effect=commands):
            search_screen.search_screen(query)
        return [(c.args[2], c.args[1], c.kwargs['compact']) for c in shown.call_args_list]

    def test_back_from_list_returns_to_results(self):
        shown = self.run_screen('alpha', ['1', 'b', 'b'], ['l'])
        self.assertEqual(shown, [('alpha', 0, False), ('', 0, True), ('alpha', 0, False)])

    def test_page_kept(self):
        shown = self.run_screen('alpha', ['n', '1', 'b', 'b'], ['l'])
        self.assertEqual(shown[-1], ('alpha', 1, False))

    def test_cyrillic_query(self):
        shown = self.run_screen('альфа', ['1', 'b', 'b'], ['l'])
        self.assertEqual(shown[-1], ('альфа', 0, False))

    def test_second_l_keeps_first_results(self):
        shown = self.run_screen('alpha', ['1', '1', 'b', 'b'], ['l', 'l'])
        self.assertEqual(shown[-1], ('alpha', 0, False))

    def test_new_search_forgets(self):
        shown = self.run_screen('alpha', ['1', 'beta', 'b'], ['l'])
        self.assertEqual([q for q, _, _ in shown], ['alpha', '', 'beta'])

    def test_new_query_from_case_forgets(self):
        shown = self.run_screen('alpha', ['1', '1', 'b'], ['l', 'gamma'])
        self.assertEqual([q for q, _, _ in shown], ['alpha', '', 'gamma'])

    def test_back_without_list_leaves(self):
        shown = self.run_screen('alpha', ['b'], [])
        self.assertEqual(shown, [('alpha', 0, False)])
