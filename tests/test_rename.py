import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import favorites, wikilinks
from core.archives import vault
from screens import search_screen


class Renamed(unittest.TestCase):
    def test_follows_first_line(self):
        self.assertEqual(vault.renamed('/v/Alpha.md', 'Alpha\nbody', 'Beta\nbody'), 'Beta')

    def test_numbered_name_follows(self):
        self.assertEqual(vault.renamed('/v/Alpha 2.md', 'Alpha', 'Beta'), 'Beta')

    def test_heading_mark(self):
        self.assertEqual(vault.renamed('/v/Alpha.md', '# Alpha', '# Beta'), 'Beta')

    def test_own_name_kept(self):
        self.assertIsNone(vault.renamed('/v/2026-01-01.md', 'Alpha', 'Beta'))
        self.assertIsNone(vault.renamed('/v/Alpha beta.md', 'Alpha', 'Gamma'))

    def test_first_line_unchanged(self):
        self.assertIsNone(vault.renamed('/v/Alpha.md', 'Alpha\none', 'Alpha\ntwo'))

    def test_empty_text(self):
        self.assertIsNone(vault.renamed('/v/Alpha.md', 'Alpha', ''))
        self.assertIsNone(vault.renamed('/v/Alpha.md', 'Alpha', ' \n '))

    def test_cyrillic(self):
        self.assertEqual(vault.renamed('/v/Альфа.md', 'Альфа', 'Бета'), 'Бета')

    def test_unsafe_characters(self):
        self.assertEqual(vault.renamed('/v/Alpha.md', 'Alpha', 'Beta: gamma/delta'), 'Beta gamma delta')


class RenameNote(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def note(self, name, text='body'):
        path = self.dir / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_renames(self):
        new = vault.rename_note(str(self.note('Alpha.md')), 'Beta')
        self.assertEqual(new, str(self.dir / 'Beta.md'))
        self.assertEqual(os.listdir(self.dir), ['Beta.md'])
        self.assertEqual(Path(new).read_text(encoding='utf-8'), 'body')

    def test_taken_name_numbered(self):
        self.note('Beta.md', 'keep')
        new = vault.rename_note(str(self.note('Alpha.md')), 'Beta')
        self.assertEqual(new, str(self.dir / 'Beta 2.md'))
        self.assertEqual((self.dir / 'Beta.md').read_text(encoding='utf-8'), 'keep')

    def test_case_only(self):
        vault.rename_note(str(self.note('alpha.md')), 'Alpha')
        self.assertEqual(os.listdir(self.dir), ['Alpha.md'])

    def test_cyrillic(self):
        vault.rename_note(str(self.note('Альфа.md')), 'Бета')
        self.assertEqual(os.listdir(self.dir), ['Бета.md'])

    def test_missing_file(self):
        with self.assertRaises(OSError):
            vault.rename_note(str(self.dir / 'none.md'), 'Beta')


NOTE = {'filepath': '/v/Alpha.md', 'text': 'Alpha', 'filename': 'Alpha'}


def _other(text, path='/v/Beta.md', **k):
    return {'filepath': path, 'text': text, **k}


class Linked(unittest.TestCase):
    def count(self, *others):
        return wikilinks.linked(NOTE['filepath'], [NOTE, *others])

    def test_link_forms(self):
        for text in ('[[Alpha]]', '[[Alpha|a]]', '[[Alpha#Top]]', '[[v/Alpha]]', '[[alpha]]', '![[Alpha]]',
                     '[[Alpha.md]]'):
            with self.subTest(text=text):
                self.assertEqual(self.count(_other(f'See {text}')), 1)

    def test_not_links(self):
        for text in ('Alpha', '[[Alpha beta]]', '[[https://example.com/Alpha]]', '[Alpha](Alpha.md)'):
            with self.subTest(text=text):
                self.assertEqual(self.count(_other(text)), 0)

    def test_self_link_ignored(self):
        self.assertEqual(wikilinks.linked('/v/Alpha.md', [dict(NOTE, text='[[Alpha]]')]), 0)

    def test_one_per_file(self):
        cards = [_other('[[Alpha]]', '/v/Board.md', lane='Todo'), _other('[[Alpha]]', '/v/Board.md', lane='Done')]
        self.assertEqual(self.count(*cards, _other('[[Alpha]]', '/v/Gamma.md')), 2)

    def test_raw_text_used(self):
        self.assertEqual(self.count(_other('plain', raw='[[Alpha]]')), 1)

    def test_cyrillic(self):
        note = {'filepath': '/v/Альфа.md', 'text': 'Альфа', 'filename': 'Альфа'}
        self.assertEqual(wikilinks.linked(note['filepath'], [note, _other('[[альфа]]')]), 1)


class Move(unittest.TestCase):
    def move(self, keys):
        cfg = {'favorites': keys}
        with mock.patch.object(favorites.config, 'load', return_value=cfg), \
             mock.patch.object(favorites.config, 'save') as save:
            favorites.move({'filepath': '/v/Alpha.md', 'element_id': 'Alpha'}, '/v/Beta.md', 'Beta')
        return save

    def test_pinned_moves(self):
        self.move([['/v/Gamma.md', 'Gamma'], ['/v/Alpha.md', 'Alpha']]).assert_called_once_with(
            {'favorites': [['/v/Gamma.md', 'Gamma'], ['/v/Beta.md', 'Beta']]})

    def test_not_pinned_untouched(self):
        self.move([['/v/Gamma.md', 'Gamma']]).assert_not_called()


class Follow(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        path = self.dir / 'Alpha.md'
        path.write_text('Alpha', encoding='utf-8')
        self.case = {'archive': vault.Vault.name, 'filepath': str(path), 'element_id': 'Alpha',
                     'filename': 'Alpha', 'source': 'Alpha.md', 'text': 'Alpha'}
        self.move = mock.patch.object(search_screen.favorites, 'move').start()
        self.addCleanup(mock.patch.stopall)

    def follow(self, text='Beta', others=()):
        with mock.patch.object(search_screen.archives, 'cases', return_value=[self.case, *others]):
            return search_screen._follow(self.case, 'Alpha', text)

    def test_renamed(self):
        self.assertIsNone(self.follow())
        new = str(self.dir / 'Beta.md')
        self.assertEqual((self.case['filepath'], self.case['element_id'], self.case['filename'], self.case['source']),
                         (new, 'Beta', 'Beta', 'Beta.md'))
        self.assertEqual(self.move.call_args.args[1:], (new, 'Beta'))

    def test_linked_keeps_name(self):
        other = {'filepath': str(self.dir / 'Gamma.md'), 'text': 'See [[Alpha]]'}
        self.assertEqual(self.follow(others=[other]), 'Name kept, linked from 1 record.')
        self.assertEqual(os.listdir(self.dir), ['Alpha.md'])
        self.move.assert_not_called()

    def test_card_and_board_block_skipped(self):
        for extra in ({'lane': 'Todo'}, {'archive': 'Board'}, {'filename': None}):
            with self.subTest(extra=extra):
                self.case.update(extra)
                self.assertIsNone(self.follow())
                self.assertEqual(os.listdir(self.dir), ['Alpha.md'])

    def test_rename_error(self):
        with mock.patch.object(search_screen, 'rename_note', side_effect=OSError('busy')):
            self.assertEqual(self.follow(), 'Name kept: could not rename the file.')
        self.assertEqual(self.case['filepath'], str(self.dir / 'Alpha.md'))

    def test_no_free_name(self):
        with mock.patch.object(search_screen, 'rename_note', return_value=None):
            self.assertEqual(self.follow(), 'Name kept: no free name for it.')

    def test_same_first_line(self):
        self.assertIsNone(self.follow('Alpha\nmore'))
        self.assertEqual(os.listdir(self.dir), ['Alpha.md'])
