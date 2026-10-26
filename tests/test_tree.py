import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from core import tree
from screens import tree_screen
from ui.interface import dim


def _names(node):
    return [n['name'] for n in tree.entries(node)]


class Build(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.vault = self.root / 'Vault'

    def note(self, *parts):
        path = self.vault.joinpath(*parts)
        return {'filepath': str(path), 'filename': path.stem, 'text': path.stem}

    def block(self, path, text):
        return {'filepath': str(path), 'element_id': text, 'text': text}

    def card(self, path, lane, text):
        return {'filepath': str(path), 'element_id': text, 'text': text, 'lane': lane}

    def test_kanban_lanes_in_board_order(self):
        board = self.vault / 'board.md'
        cases = [self.card(board, 'Todo', 'Alpha'), self.card(board, 'Done', 'Beta'),
                 self.card(board, 'Todo', 'Gamma')]
        root = tree.build([self.note('a.md'), *cases], str(self.vault))
        kanban = tree.entries(root)[1]
        self.assertEqual((kanban['name'], kanban['kind']), ('board', 'kanban'))
        self.assertEqual(_names(kanban), ['Todo', 'Done'])
        self.assertEqual([c['text'] for c in tree.entries(kanban)[0]['cases']], ['Alpha', 'Gamma'])
        self.assertEqual(tree.entries(kanban)[0]['kind'], 'lane')
        self.assertEqual(tree.count(kanban), 3)
        self.assertEqual(tree.count(root), 4)

    def test_is_branch(self):
        self.assertEqual([tree.is_branch({'kind': k}) for k in ('folder', 'kanban', 'lane', 'board', 'note')],
                         [True, True, False, False, False])

    def test_folders_first_then_alpha(self):
        cases = [self.note('beta.md'), self.note('Alpha.md'), self.note('Work', 'a.md'), self.note('archive', 'b.md')]
        root = tree.build(cases, str(self.vault))
        self.assertEqual(_names(root), ['archive', 'Work', 'Alpha', 'beta'])

    def test_counts(self):
        cases = [self.note('Work', 'a.md'), self.note('Work', 'b.md'), self.note('Work', 'Logs', 'c.md'), self.note('d.md')]
        root = tree.build(cases, str(self.vault))
        work = tree.entries(root)[0]
        self.assertEqual(tree.count(work), 3)
        self.assertEqual(tree.count(root), 4)

    def test_board_inside_vault(self):
        board = self.vault / 'Work' / 'Plan.excalidraw.md'
        root = tree.build([self.block(board, 'first'), self.block(board, 'second')], str(self.vault))
        item = tree.entries(tree.entries(root)[0])[0]
        self.assertEqual((item['name'], item['kind']), ('Plan', 'board'))
        self.assertEqual([c['text'] for c in item['cases']], ['first', 'second'])
        self.assertEqual(tree.count(root), 2)

    def test_outside_folder_named(self):
        inbox = self.root / 'Inbox'
        case = {'filepath': str(inbox / 'idea.md'), 'filename': 'idea', 'text': 'idea'}
        root = tree.build([self.note('a.md'), case], str(self.vault), [str(inbox)])
        self.assertEqual(_names(root), ['Inbox', 'a'])
        self.assertEqual(tree.entries(root)[0]['kind'], 'folder')

    def test_folder_inside_vault_in_place(self):
        notes = self.vault / 'Notes'
        root = tree.build([self.note('Notes', 'x.md')], str(self.vault), [str(notes)])
        self.assertEqual(_names(root), ['Notes'])

    def test_loose_board_at_top(self):
        board = self.root / 'Solo.excalidraw.md'
        root = tree.build([self.note('a.md'), self.block(board, 'one')], str(self.vault))
        self.assertEqual(_names(root), ['a', 'Solo'])

    def test_no_vault(self):
        boards = self.root / 'Boards'
        root = tree.build([self.block(boards / 'Map.excalidraw', 'one')], None, [str(boards)])
        self.assertEqual(_names(root), ['Boards'])
        self.assertEqual(_names(tree.entries(root)[0]), ['Map'])

    def test_without_filepath_skipped(self):
        root = tree.build([{'text': 'loose'}], str(self.vault))
        self.assertEqual(tree.entries(root), [])


class KanbanScreen(unittest.TestCase):
    BOARD = {'filepath': '/v/board.md', 'element_id': 'board', 'filename': 'board', 'text': '',
             'lanes': ['Todo', 'Done', 'Later']}
    CASES = [BOARD, *({'filepath': '/v/board.md', 'element_id': t, 'text': t, 'lane': lane}
                      for lane, t in (('Todo', 'Alpha'), ('Todo', 'Beta'), ('Done', 'Gamma')))]

    def setUp(self):
        self.root = tree.build(self.CASES, '/v')
        self.kanban = tree.entries(self.root)[0]

    def test_info(self):
        self.assertEqual(tree_screen._info(self.kanban, 0), dim('kanban · 3 cards'))
        self.assertEqual(tree_screen._info(tree.entries(self.kanban)[1], 0), dim('1 card'))

    def test_lane_keeps_board_order(self):
        self.assertEqual([c['text'] for c in tree_screen._cases(tree.entries(self.kanban)[0])], ['Alpha', 'Beta'])

    def test_lane_head(self):
        lane = tree.entries(self.kanban)[0]
        frame, _ = tree_screen._frame([self.root, self.kanban, lane], lane['cases'], 0)
        self.assertEqual(frame.splitlines()[0], dim('Archive > board > Todo   2 cards'))

    def test_empty_lane_shown_in_board_order(self):
        self.assertEqual(_names(self.kanban), ['Todo', 'Done', 'Later'])
        self.assertEqual(tree.entries(self.kanban)[2]['cases'], [])
        self.assertEqual(tree.count(self.kanban), 3)

    def test_trail(self):
        self.assertEqual(tree.trail(self.root, '/v/board.md'), ['board'])
        self.assertIsNone(tree.trail(self.root, '/v/other.md'))

    def screen(self, commands):
        with mock.patch.object(tree_screen, '_build', return_value=self.root), \
             mock.patch.object(tree_screen, 'read_command', side_effect=commands) as read, \
             mock.patch.object(tree_screen, 'clear_screen'), \
             mock.patch.object(tree_screen.archives, 'load'), \
             mock.patch.object(tree_screen.editor, 'available', return_value=True), \
             mock.patch.object(tree_screen, 'add_card') as add, \
             redirect_stdout(io.StringIO()) as out:
            tree_screen.tree_screen('/v/board.md')
        return read, add, out.getvalue()

    def test_start_opens_board_and_back_leaves(self):
        read, add, out = self.screen(['b'])
        self.assertEqual(read.call_count, 1)
        self.assertIn(dim('Archive > board'), out)
        add.assert_not_called()

    def test_add_in_lane(self):
        _, add, out = self.screen(['3', 'a', 'b', 'b'])
        add.assert_called_once_with('/v/board.md', 'Later')
        self.assertIn(dim('Archive > board > Later   0 cards'), out)
        self.assertIn('[a] add card', out)

    def test_a_ignored_on_board(self):
        _, add, out = self.screen(['a', 'b'])
        add.assert_not_called()
        self.assertNotIn('[a] add card', out)

    def test_walk_into_lane(self):
        stack = tree_screen._walk(self.root, ['board', 'Done'])
        self.assertEqual([n['kind'] for n in stack], ['folder', 'kanban', 'lane'])


if __name__ == '__main__':
    unittest.main()
