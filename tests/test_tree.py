import tempfile
import unittest
from pathlib import Path

from core import tree


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


if __name__ == '__main__':
    unittest.main()
