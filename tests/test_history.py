import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from core import history
from core.settings import PAGE_MAX
from screens import history_screen, search_screen
from ui.interface import visible

CASES = [{'text': 'Alpha', 'filepath': '/v/a.md', 'element_id': 'e1'}]
FOUND = [(0, CASES[0])]
WIDE = os.terminal_size((40, 20))
NAV = '  [number] open   [b] back   [h] help'


class _History(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(history, '_QUERIES', [])
        self.queries = patcher.start()
        self.addCleanup(patcher.stop)


class Store(_History):
    def test_newest_first(self):
        history.add('Alpha')
        history.add('Beta')
        self.assertEqual(history.recent(15), ['Beta', 'Alpha'])

    def test_duplicate_moves_up_with_new_spelling(self):
        for query in ('Alpha', 'Beta', 'alpha'):
            history.add(query)
        self.assertEqual(history.recent(15), ['alpha', 'Beta'])

    def test_cyrillic_duplicate(self):
        history.add('Альфа')
        history.add('АЛЬФА')
        self.assertEqual(history.recent(15), ['АЛЬФА'])

    def test_lines_are_kept(self):
        history.add('Alpha\nBeta')
        history.add('Alpha Beta')
        self.assertEqual(history.recent(15), ['Alpha Beta', 'Alpha\nBeta'])

    def test_capped_at_page_max(self):
        for n in range(PAGE_MAX + 5):
            history.add(f'Query {n}')
        self.assertEqual(len(self.queries), PAGE_MAX)
        self.assertEqual(self.queries[0], f'Query {PAGE_MAX + 4}')
        self.assertEqual(self.queries[-1], 'Query 5')

    def test_recent_limit_and_copy(self):
        for query in ('Alpha', 'Beta', 'Gamma'):
            history.add(query)
        shown = history.recent(2)
        self.assertEqual(shown, ['Gamma', 'Beta'])
        shown.clear()
        self.assertEqual(self.queries, ['Gamma', 'Beta', 'Alpha'])


class Recording(_History):
    def search(self, query, found, commands=('b',), opened=None, **kwargs):
        with mock.patch.object(search_screen.archives, 'cases', return_value=CASES), \
             mock.patch.object(search_screen.archives, 'load'), \
             mock.patch.object(search_screen.favorites, 'resolve', return_value=[]), \
             mock.patch.object(search_screen, 'search_separator', return_value=';'), \
             mock.patch.object(search_screen, 'page_rows', return_value=15), \
             mock.patch.object(search_screen, '_find', return_value=(found, None)) as self.find, \
             mock.patch.object(search_screen, '_suggest', return_value=[]), \
             mock.patch.object(search_screen, 'open_case', return_value=opened), \
             mock.patch.object(search_screen, 'show_list', side_effect=lambda r, page, *a, **k: page), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch.object(search_screen, 'haptic'), \
             mock.patch.object(search_screen, 'read_command', side_effect=list(commands)), \
             mock.patch('builtins.print'):
            search_screen.search_screen(query, **kwargs)
        return list(self.queries)

    def test_found_query_is_kept(self):
        self.assertEqual(self.search('Alpha', FOUND), ['Alpha'])

    def test_nothing_found_is_not_kept(self):
        self.assertEqual(self.search('Gamma', []), [])

    def test_list_is_not_kept(self):
        self.assertEqual(self.search('l', FOUND), [])
        self.find.assert_not_called()

    def test_typed_query_is_kept(self):
        self.assertEqual(self.search('Alpha', FOUND, ['Beta', 'b']), ['Beta', 'Alpha'])

    def test_query_from_record_is_kept(self):
        self.assertEqual(self.search('Alpha', FOUND, ['1', 'b'], opened='Beta'), ['Beta', 'Alpha'])

    def test_lines_are_kept(self):
        self.assertEqual(self.search('Alpha\nBeta', FOUND), ['Alpha\nBeta'])

    def test_jump_query_is_not_kept(self):
        self.assertEqual(self.search('Alpha', FOUND, remember=False), [])

    def test_typed_after_jump_is_kept(self):
        self.assertEqual(self.search('Alpha', FOUND, ['Beta', 'b'], remember=False), ['Beta'])

    def test_jump_does_not_remember(self):
        with mock.patch.object(search_screen, 'show_case', return_value=['Alpha; Beta']), \
             mock.patch.object(search_screen, 'read_command', side_effect=['j', 'b']), \
             mock.patch.object(search_screen, 'search_separator', return_value=';'), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen, 'search_screen') as search:
            search_screen.open_case(FOUND, 1, '')
        search.assert_called_once_with('Alpha  Beta', remember=False)


class Screen(_History):
    def show(self, queries, commands, rows=15, search=None):
        self.queries[:] = queries
        with mock.patch.object(history_screen, 'page_rows', return_value=rows), \
             mock.patch.object(history_screen, 'clear_screen'), \
             mock.patch.object(history_screen, 'pause') as self.pause, \
             mock.patch.object(history_screen, 'render_help') as self.help, \
             mock.patch.object(history_screen, 'search_screen', side_effect=search) as self.search, \
             mock.patch.object(history_screen, 'read_command', side_effect=list(commands)) as self.read, \
             mock.patch('shutil.get_terminal_size', return_value=WIDE), \
             redirect_stdout(io.StringIO()) as out:
            history_screen.history_screen()
        return visible(out.getvalue())

    def test_empty(self):
        text = self.show([], [])
        self.assertEqual(text, 'No searches yet.\nSearches you run show up here.\n')
        self.pause.assert_called_once_with()
        self.read.assert_not_called()

    def test_list(self):
        text = self.show(['Alpha', 'Beta\nGamma'], ['b'])
        self.assertEqual(text, f'Search history\n\n  1 Alpha\n  2 Beta Gamma\n\n{NAV}\n\n')
        self.read.assert_called_once_with('history> ')
        self.search.assert_not_called()

    def test_follows_rows_setting(self):
        text = self.show([f'Query {n}' for n in range(1, 8)], ['6', 'b'], rows=5)
        self.assertIn('  5 Query 5\n', text)
        self.assertNotIn('Query 6', text)
        self.search.assert_not_called()

    def test_two_digit_numbers(self):
        text = self.show([f'Query {n}' for n in range(1, 11)], ['b'])
        self.assertIn('\n   1 Query 1\n', text)
        self.assertIn('\n  10 Query 10\n', text)

    def test_long_query_clipped(self):
        text = self.show(['A' * 50, 'B' * 35], ['b'])
        self.assertIn('\n  1 ' + 'A' * 34 + '…\n', text)
        self.assertIn('\n  2 ' + 'B' * 35 + '\n', text)

    def test_number_runs_full_query(self):
        self.show(['Alpha', 'Beta\nGamma'], ['2', 'b'])
        self.search.assert_called_once_with('Beta\nGamma')

    def test_list_follows_new_order(self):
        text = self.show(['Alpha', 'Beta'], ['2', 'b'], search=history.add)
        frames = text.split('Search history')[1:]
        self.assertIn('  1 Alpha\n  2 Beta\n', frames[0])
        self.assertIn('  1 Beta\n  2 Alpha\n', frames[1])

    def test_garbage_is_ignored(self):
        commands = ['0', '3', '²', '٢', ' ', 'Alpha', 'b']
        self.show(['Alpha', 'Beta'], commands)
        self.search.assert_not_called()
        self.assertEqual(self.read.call_count, len(commands))
        self.assertEqual(self.queries, ['Alpha', 'Beta'])

    def test_help(self):
        self.show(['Alpha'], ['h', 'b'])
        self.help.assert_called_once_with(history_screen.HELP_SECTIONS)
        self.pause.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
