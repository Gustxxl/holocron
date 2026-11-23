import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.archives import excalidraw_obsidian as obsidian_mod
from core.archives import vault as vault_mod

DRAWING = ('---\nexcalidraw-plugin: parsed\n---\n\n## Drawing\n```json\n'
           '{"elements": [{"type": "text", "id": "t1", "text": "Alpha", "x": 0, "y": 0}]}\n```\n')


class VaultDrawings(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.vault = Path(tmp.name).resolve() / 'Vault'
        files = (('Todo.md', 'Todo'), ('Gamma.md', 'Gamma\n```json\n{"elements": []}\n```'),
                 ('Work/Альфа.excalidraw.md', DRAWING), ('Old/Beta.excalidraw.md', DRAWING))
        for rel, text in files:
            path = self.vault / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')

    def load(self, board='', exclude=()):
        with mock.patch.object(vault_mod, 'vault_path', return_value=str(self.vault)), \
             mock.patch.object(vault_mod, 'new_cases_path', return_value=''), \
             mock.patch.object(vault_mod, 'vault_exclude', return_value=list(exclude)), \
             mock.patch.object(obsidian_mod, 'archive_path', return_value=board):
            drawings, notes = obsidian_mod.ExcalidrawObsidian(), vault_mod.Vault()
            drawings.load()
            notes.load()
            configured = drawings.is_configured()
        boards = sorted(Path(c['filepath']).parent.name for c in drawings._cases)
        return configured, boards, sorted(c['filename'] for c in notes._cases)

    def test_drawings_found_without_board(self):
        self.assertEqual(self.load(), (True, ['Old', 'Work'], ['Gamma', 'Todo']))

    def test_board_inside_vault_read_once(self):
        board = str(self.vault / 'Work' / 'Альфа.excalidraw.md')
        self.assertEqual(self.load(board)[1], ['Old', 'Work'])

    def test_excluded_folder_skipped(self):
        self.assertEqual(self.load(exclude=['Old'])[1], ['Work'])

    def test_board_outside_vault(self):
        outside = self.vault.parent / 'Board.excalidraw.md'
        outside.write_text(DRAWING, encoding='utf-8')
        self.assertEqual(self.load(str(outside))[1], ['Old', 'Work', self.vault.parent.name])


class ObsidianPath(unittest.TestCase):
    def test_clear(self):
        from screens import settings_screen as s
        with mock.patch.object(s, 'archive_path', return_value='/Альфа/Board.md'), \
             mock.patch.object(s, 'vault_path', return_value=''), \
             mock.patch.object(s, 'read_command', return_value='c'), \
             mock.patch.object(s, 'update_archive_path') as update, \
             mock.patch.object(s.archives, 'load'), mock.patch.object(s, 'pause'), \
             mock.patch.object(s, 'clear_screen'), mock.patch('builtins.print'):
            s.excalidraw_obsidian_screen()
        update.assert_called_once_with('')


if __name__ == '__main__':
    unittest.main()
