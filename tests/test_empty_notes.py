import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import backups, search, tree, wikilinks
from core.archives import vault as vault_mod
from core.archives.vault import read_note
from screens import search_screen

EMPTY = '🧪 empty'
LINK = 'See [[🧪 empty]]'


class Empty(unittest.TestCase):
    def setUp(self):
        for name in ('vault', 'backups'):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            setattr(self, name, Path(tmp.name).resolve())
        (self.vault / f'{EMPTY}.md').write_text('', encoding='utf-8')
        (self.vault / 'blank.md').write_text('  \n\n', encoding='utf-8')
        (self.vault / 'linker.md').write_text(LINK, encoding='utf-8')
        patches = [mock.patch.object(backups, 'DIR', self.backups)]
        patches += [mock.patch.object(vault_mod, name, return_value=value)
                    for name, value in (('vault_path', str(self.vault)), ('new_cases_path', ''), ('vault_exclude', []))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.cases = self.load()

    def load(self):
        v = vault_mod.Vault()
        v.load()
        return v.tagged_cases()

    def case(self, name):
        return next(c for c in self.cases if c['filename'] == name)

    def edit(self, written, case=None, confirm=True):
        case = case or self.case(EMPTY)
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen.archives, 'cases', return_value=self.cases), \
             mock.patch.object(search_screen, 'trash_note', side_effect=lambda fp: Path(fp).unlink()), \
             mock.patch.object(search_screen, 'read_command', side_effect=['e', 'b']), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen, 'haptic'), \
             mock.patch.object(search_screen, 'error') as error, \
             mock.patch.object(search_screen, '_confirm', return_value=confirm) as ask, \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', return_value=written):
            search_screen.open_case([(0, case)], 1, '')
        return error, ask

    def test_empty_notes_loaded(self):
        self.assertEqual({c['filename'] for c in self.cases}, {EMPTY, 'blank', 'linker'})

    def test_blank_text(self):
        self.assertEqual(self.case('blank')['text'], '')

    def test_link_resolves(self):
        _, found = wikilinks.numbered(self.case('linker')['text'], self.cases, lambda shown, n: shown)
        self.assertEqual(found[0][0]['filename'], EMPTY)

    def test_found_by_name(self):
        self.assertIn(EMPTY, [c['filename'] for _, c in search.search(self.cases, 'empty')])

    def test_in_tree(self):
        root = tree.build(self.cases, str(self.vault))
        self.assertIn(EMPTY, [n['name'] for n in tree.entries(root)])

    def test_fill_empty_note(self):
        error, _ = self.edit('filled\n')
        error.assert_not_called()
        self.assertEqual(read_note(self.vault / f'{EMPTY}.md'), 'filled')

    def test_untouched_empty_note_offers_trash(self):
        error, ask = self.edit('\n', confirm=False)
        error.assert_not_called()
        ask.assert_called_once_with('Move the note to the trash? Linked from 1 record, those links will break.')
        self.assertEqual((self.vault / f'{EMPTY}.md').read_text(encoding='utf-8'), '')

    def test_clear_asks(self):
        _, ask = self.edit('', self.case('linker'), confirm=False)
        ask.assert_called_once_with('Move the note to the trash?')
        self.assertEqual(read_note(self.vault / 'linker.md'), LINK)

    def test_clear_moves_to_trash(self):
        self.edit('', self.case('linker'))
        self.assertFalse((self.vault / 'linker.md').exists())
        self.assertNotIn('linker', {c['filename'] for c in self.load()})

    def test_clear_leaves_nothing_behind(self):
        self.edit('', self.case('linker'))
        self.assertEqual(list(self.backups.iterdir()), [])
        self.assertEqual(sorted(p.name for p in self.vault.iterdir()), sorted([f'{EMPTY}.md', 'blank.md']))

    def test_normal_edit_not_asked(self):
        error, ask = self.edit(f'{LINK} again', self.case('linker'))
        error.assert_not_called()
        ask.assert_not_called()
        self.assertEqual(read_note(self.vault / 'linker.md'), f'{LINK} again')

    def test_board_block_not_cleared(self):
        block = {'archive': 'Excalidraw for Obsidian', 'filepath': '/v/Plan.excalidraw.md',
                 'element_id': 'a1', 'text': 'block text'}
        with mock.patch.object(search_screen, '_save') as save:
            error, _ = self.edit('', block)
        error.assert_called_once()
        save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
