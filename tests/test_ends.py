import unittest
from unittest import mock

from screens import events_screen, favorites_screen, search_screen, tasks_screen, tree_screen

CASES = [{'text': f'Block {n}', 'filepath': '/v/a.md', 'element_id': f'e{n}'} for n in range(1, 31)]


def _pages(seen, last):
    def show(results, page, *a, **k):
        seen.append(page)
        return max(0, min(page, last))
    return show


class SearchList(unittest.TestCase):
    def test_last_and_first_page(self):
        seen = []
        with mock.patch.object(search_screen.archives, 'cases', return_value=CASES), \
             mock.patch.object(search_screen.archives, 'load'), \
             mock.patch.object(search_screen.favorites, 'resolve', return_value=[]), \
             mock.patch.object(search_screen, 'page_rows', return_value=15), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch.object(search_screen, 'pause') as pause, \
             mock.patch.object(search_screen, 'show_list', side_effect=_pages(seen, 1)), \
             mock.patch.object(search_screen, 'read_command', side_effect=['nn', 'pp', 'nn', 'p', 'b']):
            search_screen.search_screen('l')
        self.assertEqual(seen, [0, 30, 0, 30, 0])
        pause.assert_not_called()


class Records(unittest.TestCase):
    def test_last_and_first_record(self):
        shown = []
        results = [(0, c) for c in CASES[:4]]
        with mock.patch.object(search_screen, 'show_case', side_effect=lambda case, *a, **k: shown.append(case['text']) or []), \
             mock.patch.object(search_screen, 'read_command', side_effect=['nn', 'nn', 'pp', 'pp', 'b']):
            self.assertIsNone(search_screen.open_case(results, 2, ''))
        self.assertEqual(shown, ['Block 2', 'Block 4', 'Block 4', 'Block 1', 'Block 1'])

    def test_not_a_query(self):
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen, 'read_command', side_effect=['nn', 'b']) as read:
            self.assertIsNone(search_screen.open_case([(0, CASES[0])], 1, ''))
        self.assertEqual(read.call_count, 2)


class Tree(unittest.TestCase):
    def test_last_and_first_page(self):
        seen = []

        def frame(stack, items, page, *a):
            seen.append(page)
            return '', max(0, min(page, 1))

        with mock.patch.object(tree_screen, '_build', return_value=tree_screen.tree.build(CASES, '/v')), \
             mock.patch.object(tree_screen, '_frame', side_effect=frame), \
             mock.patch.object(tree_screen, 'clear_screen'), \
             mock.patch.object(tree_screen, 'read_command', side_effect=['1', 'nn', 'pp', 'b', 'b']), \
             mock.patch('builtins.print'):
            tree_screen.tree_screen()
        self.assertEqual(seen, [0, 0, 30, 0, 0])


class Favorites(unittest.TestCase):
    def test_last_and_first_page(self):
        seen = []
        with mock.patch.object(favorites_screen.favorites, 'resolve', return_value=CASES), \
             mock.patch.object(favorites_screen.archives, 'cases', return_value=CASES), \
             mock.patch.object(favorites_screen, 'show_list', side_effect=_pages(seen, 2)), \
             mock.patch.object(favorites_screen, 'read_command', side_effect=['nn', 'pp', 'b']):
            favorites_screen.favorites_screen()
        self.assertEqual(seen, [0, 30, 0])


class Cards(unittest.TestCase):
    def run_open(self, module, call):
        seen = []
        with mock.patch.object(module, '_card', side_effect=lambda item, number, *a: seen.append(number) or []), \
             mock.patch.object(module, 'clear_screen'), \
             mock.patch.object(module, 'read_command', side_effect=['nn', 'nn', 'pp', 'b']), \
             mock.patch('builtins.print'):
            call()
        return seen

    def test_events(self):
        seen = self.run_open(events_screen, lambda: events_screen._open([{}, {}, {}], 2))
        self.assertEqual(seen, [2, 3, 3, 1])

    def test_tasks(self):
        with mock.patch.object(tasks_screen.waypoints, 'load', return_value={}):
            seen = self.run_open(tasks_screen, lambda: tasks_screen._open(None, [{}, {}, {}], 2))
        self.assertEqual(seen, [2, 3, 3, 1])


if __name__ == '__main__':
    unittest.main()
