import unittest
from unittest import mock

from core import settings
from screens import search_screen
from ui.interface import pick

CASES = [{'text': name, 'filepath': f'/v/{name}.md', 'element_id': name} for name in ('Alpha', 'Beta', 'Gamma')]
RESULTS = [(0, c) for c in CASES]


class Pick(unittest.TestCase):
    def test_in_range(self):
        self.assertEqual(pick('2', 3), 2)

    def test_spaces_ignored(self):
        self.assertEqual(pick(' 3 ', 3), 3)

    def test_out_of_range(self):
        for text in ('0', '4', '503'):
            with self.subTest(text=text):
                self.assertIsNone(pick(text, 3))

    def test_superscript_and_other_scripts_refused(self):
        for text in ('²', '٣', '1²'):
            with self.subTest(text=text):
                self.assertIsNone(pick(text, 9))

    def test_not_a_number(self):
        for text in ('', 'x', '-1', '1.5'):
            with self.subTest(text=text):
                self.assertIsNone(pick(text, 9))


class Search(unittest.TestCase):
    def run_search(self, *commands):
        with mock.patch.object(search_screen.archives, 'cases', return_value=CASES), \
             mock.patch.object(search_screen.archives, 'load'), \
             mock.patch.object(search_screen, 'search_separator', return_value=';'), \
             mock.patch.object(search_screen, '_find', return_value=(RESULTS, None)) as find, \
             mock.patch.object(search_screen, '_exact', return_value=None), \
             mock.patch.object(search_screen, 'show_list', return_value=0), \
             mock.patch.object(search_screen, 'open_case', return_value=None) as opened, \
             mock.patch.object(search_screen, 'read_command', side_effect=[*commands, 'b']), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch.object(search_screen, 'pause'), \
             mock.patch('builtins.print'):
            search_screen.search_screen('504')
        return [c.args[1] for c in find.call_args_list], opened

    def test_number_over_count_searches(self):
        queries, opened = self.run_search('503')
        self.assertEqual(queries, ['504', '503'])
        opened.assert_not_called()

    def test_number_in_range_opens(self):
        queries, opened = self.run_search('2')
        self.assertEqual(queries, ['504'])
        opened.assert_called_once_with(RESULTS, 2, '504')

    def test_superscript_does_not_crash(self):
        queries, opened = self.run_search('²')
        self.assertEqual(queries, ['504'])
        opened.assert_not_called()


class OpenCase(unittest.TestCase):
    def run_case(self, *commands):
        with mock.patch.object(search_screen, 'show_case', return_value=[]) as shown, \
             mock.patch.object(search_screen, 'read_command', side_effect=[*commands, 'b']), \
             mock.patch.object(search_screen, 'search_separator', return_value=';'):
            return search_screen.open_case(RESULTS, 1, '504'), shown

    def test_number_over_count_searches(self):
        new, _ = self.run_case('503')
        self.assertEqual(new, '503')

    def test_number_in_range_moves(self):
        new, shown = self.run_case('3')
        self.assertIsNone(new)
        self.assertEqual(shown.call_args.args[2], 3)


class Reorder(unittest.TestCase):
    def test_order(self):
        self.assertEqual(settings.reorder(['a', 'b', 'c'], '31'), ['c', 'a', 'b'])

    def test_superscript_refused(self):
        self.assertIsNone(settings.reorder(['a', 'b'], '²'))

    def test_empty_refused(self):
        self.assertIsNone(settings.reorder(['a', 'b'], ''))
