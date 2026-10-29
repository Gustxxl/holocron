import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.archives import vault
from screens import search_screen


class Trash(unittest.TestCase):
    def test_sends_to_trash(self):
        with mock.patch.object(vault, 'send2trash') as send:
            vault.trash_note('/v/Alpha.md')
        send.assert_called_once_with('/v/Alpha.md')


class Notes(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        mock.patch.object(search_screen.archives, 'load').start()
        mock.patch.object(search_screen.archives, 'cases', return_value=[]).start()
        mock.patch.object(search_screen, 'haptic').start()
        self.addCleanup(mock.patch.stopall)

    def note(self, name='Alpha', text='Alpha'):
        path = self.dir / f'{name}.md'
        path.write_text(text, encoding='utf-8')
        return {'archive': vault.Vault.name, 'filepath': str(path), 'element_id': name, 'filename': name,
                'source': path.name, 'text': text}


class Delete(Notes):
    def delete(self, case, answer=True, others=()):
        search_screen.archives.cases.return_value = [case, *others]
        with mock.patch.object(search_screen, '_confirm', return_value=answer) as confirm, \
             mock.patch.object(search_screen, 'trash_note', side_effect=lambda fp: Path(fp).unlink()) as trash, \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False):
            done = search_screen._delete(case)
        return done, confirm.call_args.args[0], trash

    def test_moved_to_trash(self):
        case = self.note()
        done, prompt, trash = self.delete(case)
        self.assertTrue(done)
        self.assertEqual(prompt, 'Move the note to the trash?')
        trash.assert_called_once_with(case['filepath'])
        self.assertFalse(Path(case['filepath']).exists())

    def test_cancelled(self):
        case = self.note()
        done, _, trash = self.delete(case, answer=False)
        self.assertFalse(done)
        trash.assert_not_called()
        self.assertTrue(Path(case['filepath']).exists())

    def test_links_named_in_question(self):
        case = self.note()
        other = {'filepath': str(self.dir / 'Beta.md'), 'text': 'See [[Alpha]]'}
        _, prompt, _ = self.delete(case, others=[other])
        self.assertEqual(prompt, 'Move the note to the trash? Linked from 1 record, those links will break.')

    def test_trash_error_keeps_note(self):
        case = self.note()
        with mock.patch.object(search_screen, '_confirm', return_value=True), \
             mock.patch.object(search_screen, 'trash_note', side_effect=OSError('no trash here')), \
             mock.patch.object(search_screen, 'error') as error:
            self.assertFalse(search_screen._delete(case))
        error.assert_called_once_with('Could not delete: no trash here')
        self.assertTrue(Path(case['filepath']).exists())

    def test_pinned_note_unpinned(self):
        case = self.note()
        with mock.patch.object(search_screen, '_confirm', return_value=True), \
             mock.patch.object(search_screen, 'trash_note'), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=True), \
             mock.patch.object(search_screen.favorites, 'toggle') as toggle:
            search_screen._delete(case)
        toggle.assert_called_once_with(case)

    def test_cyrillic_name(self):
        case = self.note('Альфа', 'Альфа')
        self.assertTrue(self.delete(case)[0])
        self.assertEqual(list(self.dir.iterdir()), [])


class Edit(Notes):
    def edit(self, results, edited, answer=True, commands=('e', 'b')):
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', return_value=edited), \
             mock.patch.object(search_screen, '_confirm', return_value=answer) as confirm, \
             mock.patch.object(search_screen, 'trash_note', side_effect=lambda fp: Path(fp).unlink()) as trash, \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             mock.patch.object(search_screen, 'error') as error, \
             mock.patch.object(search_screen, 'read_command', side_effect=list(commands)) as read:
            out = search_screen.open_case(results, 1, '')
        return out, trash, confirm, error, read

    def test_cleared_note_deleted(self):
        case = self.note()
        out, trash, _, _, read = self.edit([(0, case)], '')
        self.assertIsNone(out)
        trash.assert_called_once_with(case['filepath'])
        self.assertEqual(read.call_count, 1)

    def test_spaces_count_as_empty(self):
        _, trash, _, _, _ = self.edit([(0, self.note())], ' \n \n')
        trash.assert_called_once()

    def test_cancel_keeps_note_and_text(self):
        case = self.note()
        _, trash, _, _, read = self.edit([(0, case)], '', answer=False)
        trash.assert_not_called()
        self.assertEqual(Path(case['filepath']).read_text(encoding='utf-8'), 'Alpha')
        self.assertEqual(read.call_count, 2)

    def test_next_record_opens(self):
        first, second = self.note('Alpha'), self.note('Beta', 'Beta')
        with mock.patch.object(search_screen, 'show_case', return_value=[]):
            self.edit([(0, first), (0, second)], '')
        self.assertTrue(Path(second['filepath']).exists())

    def test_empty_note_offered_without_change(self):
        case = self.note(text='')
        _, trash, confirm, _, _ = self.edit([(0, case)], '')
        confirm.assert_called_once()
        trash.assert_called_once()

    def test_board_block_not_deleted(self):
        block = {'archive': 'Board', 'filepath': str(self.dir / 'b.excalidraw'), 'element_id': 'x1', 'text': 'Alpha'}
        _, trash, confirm, error, _ = self.edit([(0, block)], '')
        trash.assert_not_called()
        confirm.assert_not_called()
        error.assert_called_once_with('Empty text — edit cancelled')

    def test_unchanged_text_does_nothing(self):
        _, trash, confirm, _, _ = self.edit([(0, self.note())], 'Alpha')
        trash.assert_not_called()
        confirm.assert_not_called()


class Deleted(Notes):
    def test_detects_removed_note(self):
        case = self.note()
        self.assertFalse(search_screen._deleted(case))
        Path(case['filepath']).unlink()
        self.assertTrue(search_screen._deleted(case))

    def test_board_block_never_deleted(self):
        self.assertFalse(search_screen._deleted({'filepath': '/none/b.excalidraw', 'text': 'Alpha'}))
