import os
import re
import unittest
from unittest import mock
import io
from contextlib import redirect_stdout

from screens import search_screen, tree_screen

_ANSI = re.compile(r'\x1b\[[0-9;]*m')
SIZE = os.terminal_size((81, 24))
CASES = [{'text': f'Block {n}', 'filepath': '/v/Board.md', 'element_id': f'e{n}'} for n in range(1, 13)]
STACK = [{'name': 'Work', 'kind': 'folder'}, {'name': 'Board', 'kind': 'board', 'cases': CASES}]
MIXED = [{'text': t, 'filepath': '/v/Board.md', 'element_id': f'm{n}'}
         for n, t in enumerate(('delta', 'Alpha', 'charlie', 'Bravo'))]
NAMES = ['Alpha', 'Bravo', 'charlie', 'delta']


def _plain(text):
    return _ANSI.sub('', text)


def _printed(results, **kw):
    with mock.patch('shutil.get_terminal_size', return_value=SIZE), \
         mock.patch.object(search_screen, 'clear_screen'), \
         mock.patch('builtins.print') as out:
        search_screen.show_list(results, 0, kw.pop('query', ''), search_screen.LIST_PAGE, **kw)
    return [_plain(str(c.args[0])) if c.args else '' for c in out.call_args_list]


def _tree():
    with mock.patch('shutil.get_terminal_size', return_value=SIZE):
        frame, _ = tree_screen._frame(STACK, CASES, 0)
    return _plain(frame).split('\n')


class Rows(unittest.TestCase):
    def test_compact_aligned(self):
        rows = [_plain(r) for r in search_screen.list_rows(CASES[:3], 0, 12, 80)]
        self.assertEqual(rows, ['   1 Block 1', '   2 Block 2', '   3 Block 3'])

    def test_wrap_indent(self):
        row = _plain(search_screen.list_rows([{'text': 'word ' * 30}], 0, 12, 40)[0]).split('\n')
        self.assertGreater(len(row), 1)
        self.assertTrue(all(ln.startswith(' ' * 5) for ln in row[1:]))


class Same(unittest.TestCase):
    def test_tree_board_matches_list(self):
        listed = [ln for ln in _printed([(0, c) for c in CASES]) if 'Block' in ln]
        self.assertEqual([ln for ln in _tree() if 'Block' in ln], listed)

    def test_no_blank_between_rows(self):
        printed = _printed([(0, c) for c in CASES])
        block_lines = [ln for ln in printed if 'Block' in ln]
        self.assertEqual(len(block_lines), 12)

    def test_board_head_count(self):
        self.assertEqual(_tree()[0], 'Work > Board   12 blocks')

    def test_help_in_list(self):
        self.assertIn('help', _printed([(0, c) for c in CASES])[-2])

    def test_one_case(self):
        self.assertIn('1 case', _printed([(0, CASES[0])])[0])

    def test_similar_separator(self):
        printed = _printed([(0, c) for c in CASES[:4]], query='block', exact=2)
        i = printed.index('  Similar')
        self.assertEqual(printed[i - 1], '')
        self.assertIn('Block 2', printed[i - 2])
        self.assertIn('Block 3', printed[i + 1])


class Order(unittest.TestCase):
    def test_by_name(self):
        self.assertEqual([c['text'] for c in search_screen.by_name(MIXED)], NAMES)

    def test_list_by_name(self):
        with mock.patch.object(search_screen.favorites, 'resolve', return_value=[]):
            self.assertEqual([c['text'] for _, c in search_screen._all(MIXED)], NAMES)

    def test_pinned_first(self):
        with mock.patch.object(search_screen.favorites, 'resolve', return_value=[MIXED[0]]):
            self.assertEqual([c['text'] for _, c in search_screen._all(MIXED)], ['delta', *NAMES[:3]])

    def test_tree_board_by_name(self):
        seen = []
        with mock.patch.object(tree_screen, '_build', return_value=tree_screen.tree.build(MIXED, '/v')), \
             mock.patch.object(tree_screen, '_frame', side_effect=lambda s, items, p: (seen.append(items), ('', p))[1]), \
             mock.patch.object(tree_screen, 'clear_screen'), \
             mock.patch.object(tree_screen, 'read_command', side_effect=['1', 'b', 'b']), \
             mock.patch('builtins.print'):
            tree_screen.tree_screen()
        self.assertEqual([c['text'] for c in seen[1]], NAMES)

    def test_tree_opens_same_record(self):
        opened = []
        with mock.patch.object(tree_screen, '_build', return_value=tree_screen.tree.build(MIXED, '/v')), \
             mock.patch.object(tree_screen, '_frame', side_effect=lambda s, items, p: ('', p)), \
             mock.patch.object(tree_screen, 'clear_screen'), \
             mock.patch.object(tree_screen, 'read_command', side_effect=['1', '1', 'b', 'b']), \
             mock.patch.object(tree_screen, 'open_case', side_effect=lambda r, n, *a, **k: opened.append(r[n - 1][1])), \
             mock.patch('builtins.print'):
            tree_screen.tree_screen()
        self.assertEqual(opened[0]['text'], 'Alpha')


class Gap(unittest.TestCase):
    def test_blank_between_results(self):
        cases = [(1, {'text': 'alpha', 'filepath': '/x/a.md'}),
                 (1, {'text': 'bravo', 'filepath': '/x/b.md'})]
        out = io.StringIO()
        with mock.patch('screens.search_screen.clear_screen'), \
             mock.patch('shutil.get_terminal_size', return_value=SIZE), \
             redirect_stdout(out):
            search_screen.show_list(cases, 0, '')
        lines = [_ANSI.sub('', ln) for ln in out.getvalue().splitlines()]
        i = next(n for n, line in enumerate(lines) if 'alpha' in line)
        self.assertEqual(lines[i + 1].strip(), '')
        self.assertIn('bravo', lines[i + 2])


if __name__ == '__main__':
    unittest.main()
