import os
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

    def open(self, commands, case, written=None, confirm=True):
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen.archives, 'cases', return_value=self.cases), \
             mock.patch.object(search_screen, 'trash_note', side_effect=lambda fp: Path(fp).unlink()) as trash, \
             mock.patch.object(search_screen, 'read_command', side_effect=[*commands, 'b']), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen, 'haptic'), \
             mock.patch.object(search_screen, 'error') as error, \
             mock.patch.object(search_screen, 'confirm', return_value=confirm) as ask, \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', return_value=written):
            search_screen.open_case([(0, case)], 1, '')
        return error, ask, trash

    def edit(self, written, case=None, confirm=True):
        error, ask, trash = self.open(['e'], case or self.case(EMPTY), written, confirm)
        trash.assert_not_called()
        return error, ask

    def delete(self, case, confirm=True):
        _, ask, trash = self.open(['d'], case, confirm=confirm)
        return ask, trash

    def nav(self, case):
        with mock.patch('shutil.get_terminal_size', return_value=os.terminal_size((200, 50))), \
             mock.patch.object(search_screen.archives, 'cases', return_value=self.cases), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.keeper, 'configured', return_value=[]), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch('builtins.print') as printed:
            search_screen.show_case(case)
        return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)

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

    def test_untouched_empty_note_not_asked(self):
        error, ask = self.edit('\n')
        error.assert_not_called()
        ask.assert_not_called()
        self.assertEqual((self.vault / f'{EMPTY}.md').read_text(encoding='utf-8'), '')

    def test_clear_asks(self):
        _, ask = self.edit('', self.case('linker'), confirm=False)
        ask.assert_called_once_with('Clear all text in linker?')
        self.assertEqual(read_note(self.vault / 'linker.md'), LINK)

    def test_clear_keeps_note(self):
        error, _ = self.edit('', self.case('linker'))
        error.assert_not_called()
        self.assertEqual(read_note(self.vault / 'linker.md'), '')
        self.assertIn('linker', {c['filename'] for c in self.load()})

    def test_delete_asks(self):
        ask, trash = self.delete(self.case(EMPTY), confirm=False)
        ask.assert_called_once_with(f'Delete {EMPTY}? It goes to the trash. Linked from 1 record, those links will break.')
        trash.assert_not_called()
        self.assertTrue((self.vault / f'{EMPTY}.md').exists())

    def test_delete_moves_to_trash(self):
        ask, _ = self.delete(self.case('linker'))
        ask.assert_called_once_with('Delete linker? It goes to the trash.')
        self.assertNotIn('linker', {c['filename'] for c in self.load()})
        self.assertEqual(list(self.backups.iterdir()), [])
        self.assertEqual(sorted(p.name for p in self.vault.iterdir()), sorted([f'{EMPTY}.md', 'blank.md']))

    def test_delete_only_notes(self):
        block = {'archive': 'Excalidraw for Obsidian', 'filepath': '/v/Plan.excalidraw.md',
                 'element_id': 'a1', 'text': 'block text'}
        card = {'archive': vault_mod.Vault.name, 'filepath': '/v/Board.md', 'filename': 'Board',
                'lane': 'Todo', 'raw': 'Alpha', 'text': 'Alpha'}
        for case in (block, card):
            with self.subTest(case=case['filepath']):
                ask, trash = self.delete(case)
                ask.assert_not_called()
                trash.assert_not_called()

    def test_delete_in_nav(self):
        self.assertIn('[d] delete', self.nav(self.case('linker')))
        self.assertNotIn('[d] delete', self.nav({'text': 'Alpha', 'archive': 'Board', 'source': 'board.excalidraw'}))

    def test_card_not_cleared(self):
        card = {'archive': vault_mod.Vault.name, 'filepath': '/v/Board.md', 'filename': 'Board',
                'element_id': 'c1', 'lane': 'Todo', 'raw': 'Alpha', 'text': 'Alpha'}
        with mock.patch.object(search_screen, '_save') as save:
            error, ask = self.edit('', card)
        error.assert_called_once()
        ask.assert_not_called()
        save.assert_not_called()

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
