import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.archives import vault as vault_mod
from core.archives.vault import Vault, read_note
from screens import search_screen

TEXT = '\n- [ ] one\n- [ ] two  \n\n'


class Save(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.path = self.root / 'note.md'
        self.path.write_text(TEXT, encoding='utf-8')

    def case(self):
        return {'archive': Vault.name, 'filepath': str(self.path), 'text': read_note(self.path)}

    def test_read_note_strips(self):
        self.assertEqual(read_note(self.path), '- [ ] one\n- [ ] two')

    def test_loaded_text_matches_disk(self):
        with mock.patch.object(vault_mod, 'vault_path', return_value=str(self.root)), \
             mock.patch.object(vault_mod, 'new_cases_path', return_value=''), \
             mock.patch.object(vault_mod, 'vault_exclude', return_value=[]):
            v = vault_mod.Vault()
            v.load()
        self.assertEqual(v._cases[0]['text'], read_note(self.path))

    def test_saves_unchanged_note(self):
        case = self.case()
        search_screen._save(case, '- [x] one\n- [ ] two')
        self.assertEqual(read_note(self.path), '- [x] one\n- [ ] two')
        self.assertEqual(case['text'], '- [x] one\n- [ ] two')

    def test_refuses_note_changed_on_disk(self):
        case = self.case()
        self.path.write_text('- [x] one\n- [ ] two\nadded in Obsidian\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            search_screen._save(case, '- [ ] one\n- [x] two')
        self.assertIn('added in Obsidian', read_note(self.path))

    def test_second_save_after_first(self):
        case = self.case()
        search_screen._save(case, '- [x] one\n- [ ] two')
        search_screen._save(case, '- [x] one\n- [x] two')
        self.assertEqual(read_note(self.path), '- [x] one\n- [x] two')


class Create(unittest.TestCase):
    def test_note_command_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with mock.patch.object(search_screen.editor, 'edit_text', return_value='Disk full\nclean /var/log\n'), \
                 mock.patch.object(search_screen, 'new_cases_path', return_value=str(folder)), \
                 mock.patch.object(search_screen, 'haptic'), \
                 mock.patch.object(search_screen.archives, 'load'), \
                 mock.patch.object(search_screen.archives, 'cases', return_value=[]):
                search_screen.create_case()
            self.assertEqual(read_note(folder / 'Disk full.md'), 'Disk full\nclean /var/log')


if __name__ == '__main__':
    unittest.main()
