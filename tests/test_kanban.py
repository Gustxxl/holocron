import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from core import backups, kanban, wikilinks
from core.archives import vault as vault_mod
from core.archives.vault import Vault, read_note
from screens import search_screen
from ui.interface import dim, num


def setUpModule():
    tmp = tempfile.TemporaryDirectory()
    patch = mock.patch.object(backups, 'DIR', Path(tmp.name))
    patch.start()
    unittest.addModuleCleanup(patch.stop)
    unittest.addModuleCleanup(tmp.cleanup)


LINES = [
    '---', '', 'kanban-plugin: board', '', '---', '',
    '## Todo', '',
    '- [ ] Alpha',
    '- [ ] Beta ^ab1',
    '', '',
    '## Done (10)', '',
    '**Complete**',
    '- [x] Gamma',
    '    Gamma note',
    '- [x] Delta<br>Delta note',
    '', '',
    '## Later', '', '', '',
    '## Archive', '',
    '- [ ] Epsilon',
    '\tLine one',
    '\t',
    '\tLine two',
    '', '',
    '%% kanban:settings', '```', '{"kanban-plugin":"board"}', '```', '%%',
]
BOARD = '\n'.join(LINES)
TITLES = ['Todo', 'Done', 'Later', 'Archive']
TODO, DONE, LATER, ARCHIVE = TITLES
EPSILON = 'Epsilon\nLine one\n\nLine two'


def _join(*parts):
    return '\n'.join(ln for part in parts for ln in part)


class IsBoard(unittest.TestCase):
    def test_plugin_board(self):
        self.assertTrue(kanban.is_board(BOARD))

    def test_plain_note(self):
        self.assertFalse(kanban.is_board('## A\n- [ ] x'))

    def test_other_front_matter(self):
        self.assertFalse(kanban.is_board('---\ntags: x\n---\nkanban-plugin: board'))

    def test_key_without_value(self):
        self.assertFalse(kanban.is_board('---\nkanban-plugin:\n---\n## A'))

    def test_empty(self):
        self.assertFalse(kanban.is_board(''))


class Parse(unittest.TestCase):
    def setUp(self):
        self.lanes = kanban.parse(BOARD)

    def test_titles_in_order_without_limit(self):
        self.assertEqual(kanban.titles(BOARD), TITLES)

    def test_complete_lane(self):
        self.assertEqual([lane['complete'] for lane in self.lanes], [False, True, False, False])

    def test_card_texts(self):
        self.assertEqual([[c['text'] for c in lane['cards']] for lane in self.lanes], [
            ['Alpha', 'Beta'],
            ['Gamma\nGamma note', 'Delta\nDelta note'],
            [],
            [EPSILON],
        ])

    def test_block_id_and_check(self):
        card = self.lanes[0]['cards'][1]
        self.assertEqual((card['block'], card['check'], card['mark']), ('ab1', ' ', '- [ ] '))
        self.assertIsNone(self.lanes[0]['cards'][0]['block'])
        self.assertEqual(self.lanes[1]['cards'][0]['check'], 'x')

    def test_card_ranges(self):
        self.assertEqual([(c['start'], c['end']) for lane in self.lanes for c in lane['cards']],
                         [(8, 9), (9, 10), (15, 17), (17, 18), (26, 30)])

    def test_settings_block_ends_board(self):
        self.assertEqual(kanban.titles(BOARD + '\n## Hidden\n- [ ] x'), TITLES)

    def test_bold_after_card_is_not_complete(self):
        lanes = kanban.parse('## A\n- [ ] one\n**Complete**')
        self.assertFalse(lanes[0]['complete'])

    def test_limit_only_title_kept(self):
        self.assertEqual(kanban.titles('## (5)\n## Items (2024)'), ['(5)', 'Items'])

    def test_cards_before_heading_ignored(self):
        self.assertEqual(kanban.parse('- [ ] loose\n## A'),
                         [{'title': 'A', 'head': 1, 'complete': False, 'cards': []}])

    def test_empty_card(self):
        card = kanban.parse('## A\n- [ ]')[0]['cards'][0]
        self.assertEqual((card['text'], card['mark']), ('', '- [ ]'))

    def test_plain_item_without_checkbox(self):
        card = kanban.parse('## A\n- one')[0]['cards'][0]
        self.assertEqual((card['text'], card['check'], card['mark']), ('one', None, '- '))

    def test_garbage(self):
        self.assertEqual(kanban.parse(''), [])
        self.assertEqual(kanban.parse('just text\n***\n%%'), [])


class Replace(unittest.TestCase):
    def test_multiline_uses_board_indent(self):
        out = kanban.replace(BOARD, TODO, 'Alpha', 'Alpha\nAlpha note')
        self.assertEqual(out, _join(LINES[:8], ['- [ ] Alpha', '\tAlpha note'], LINES[9:]))

    def test_keeps_block_id(self):
        out = kanban.replace(BOARD, TODO, 'Beta', 'Beta 2')
        self.assertEqual(out, _join(LINES[:9], ['- [ ] Beta 2 ^ab1'], LINES[10:]))

    def test_br_card_rewritten_with_newlines(self):
        out = kanban.replace(BOARD, DONE, 'Delta\nDelta note', 'Delta\nNew note')
        self.assertEqual(out, _join(LINES[:17], ['- [x] Delta', '\tNew note'], LINES[18:]))

    def test_spaces_when_board_has_no_tabs(self):
        board = '---\nkanban-plugin: board\n---\n## A\n- [ ] one\n'
        self.assertEqual(kanban.replace(board, 'A', 'one', 'one\n\ntwo'),
                         '---\nkanban-plugin: board\n---\n## A\n- [ ] one\n    \n    two\n')

    def test_roundtrip_unchanged(self):
        self.assertEqual(kanban.replace(BOARD, ARCHIVE, EPSILON, EPSILON), BOARD)

    def test_missing_card(self):
        self.assertIsNone(kanban.replace(BOARD, TODO, 'Gamma', 'x'))

    def test_missing_lane(self):
        self.assertIsNone(kanban.replace(BOARD, 'Nowhere', 'Alpha', 'x'))


class Move(unittest.TestCase):
    def test_down_into_complete_ticks(self):
        out = kanban.move(BOARD, TODO, 'Alpha', 1)
        self.assertEqual(out, _join(LINES[:8], LINES[9:18], ['- [x] Alpha'], LINES[18:]))

    def test_out_of_complete_unticks_into_empty_lane(self):
        out = kanban.move(BOARD, DONE, 'Gamma\nGamma note', 2)
        self.assertEqual(out, _join(LINES[:15], LINES[17:21], ['- [ ] Gamma', '\tGamma note'], LINES[21:]))

    def test_up_keeps_mark(self):
        out = kanban.move(BOARD, ARCHIVE, EPSILON, 0)
        self.assertEqual(out, _join(LINES[:10], LINES[26:30], LINES[10:26], LINES[30:]))

    def test_keeps_block_id(self):
        out = kanban.move(BOARD, TODO, 'Beta', 3)
        self.assertEqual(out, _join(LINES[:9], LINES[10:30], ['- [ ] Beta ^ab1'], LINES[30:]))

    def test_same_lane_unchanged(self):
        self.assertEqual(kanban.move(BOARD, TODO, 'Alpha', 0), BOARD)

    def test_missing_card(self):
        self.assertIsNone(kanban.move(BOARD, TODO, 'Missing', 1))

    def test_target_out_of_range(self):
        self.assertIsNone(kanban.move(BOARD, TODO, 'Alpha', 4))
        self.assertIsNone(kanban.move(BOARD, TODO, 'Alpha', -1))

    def test_plain_item_keeps_mark(self):
        board = '---\nkanban-plugin: board\n---\n## A\n- one\n## B\n**Complete**\n'
        self.assertEqual(kanban.move(board, 'A', 'one', 1),
                         '---\nkanban-plugin: board\n---\n## A\n## B\n**Complete**\n- one\n')


class Add(unittest.TestCase):
    def test_into_empty_lane(self):
        out = kanban.add(BOARD, LATER, 'Zeta\nsoon')
        self.assertEqual(out, _join(LINES[:21], ['- [ ] Zeta', '\tsoon'], LINES[21:]))

    def test_end_of_complete_lane_ticked(self):
        out = kanban.add(BOARD, DONE, '  Eta  ')
        self.assertEqual(out, _join(LINES[:18], ['- [x] Eta'], LINES[18:]))

    def test_missing_lane(self):
        self.assertIsNone(kanban.add(BOARD, 'Nowhere', 'x'))

    def test_empty_text(self):
        self.assertIsNone(kanban.add(BOARD, TODO, ' \n '))


class Cyrillic(unittest.TestCase):
    BOARD = '---\nkanban-plugin: board\n---\n## Список (3)\n- [ ] Альфа\n\tёлка\n## Готово\n**Complete**\n'

    def test_parse(self):
        lanes = kanban.parse(self.BOARD)
        self.assertEqual([lane['title'] for lane in lanes], ['Список', 'Готово'])
        self.assertEqual(lanes[0]['cards'][0]['text'], 'Альфа\nёлка')

    def test_replace(self):
        self.assertEqual(kanban.replace(self.BOARD, 'Список', 'Альфа\nёлка', 'Бета'),
                         '---\nkanban-plugin: board\n---\n## Список (3)\n- [ ] Бета\n## Готово\n**Complete**\n')

    def test_move(self):
        self.assertEqual(kanban.move(self.BOARD, 'Список', 'Альфа\nёлка', 1),
                         '---\nkanban-plugin: board\n---\n## Список (3)\n## Готово\n**Complete**\n- [x] Альфа\n\tёлка\n')


class Load(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def load(self):
        with mock.patch.object(vault_mod, 'vault_path', return_value=str(self.root)), \
             mock.patch.object(vault_mod, 'new_cases_path', return_value=''), \
             mock.patch.object(vault_mod, 'vault_exclude', return_value=[]):
            v = vault_mod.Vault()
            v.load()
        return v._cases

    def test_cards_are_records(self):
        (self.root / 'board.md').write_text(BOARD, encoding='utf-8')
        (self.root / 'note.md').write_text('## Alpha\nplain note', encoding='utf-8')
        cases = self.load()
        cards = [c for c in cases if 'lane' in c]
        self.assertEqual([(c['lane'], c['raw']) for c in cards], [
            (TODO, 'Alpha'), (TODO, 'Beta'),
            (DONE, 'Gamma\nGamma note'), (DONE, 'Delta\nDelta note'),
            (ARCHIVE, EPSILON),
        ])
        self.assertEqual([c['element_id'] for c in cards], ['Alpha', 'ab1', 'Gamma', 'Delta', 'Epsilon'])
        self.assertTrue(all('filename' not in c and c['source'] == 'board.md' for c in cards))
        self.assertEqual([c['filename'] for c in cases if 'lane' not in c], ['board', 'note'])
        board = cases[0]
        self.assertEqual((board['lanes'], board['text'], board['element_id']), (TITLES, '\n'.join(TITLES), 'board'))

    def test_emoji_only_skipped_and_duplicates_numbered(self):
        board = '---\nkanban-plugin: board\n---\n## A\n- [ ] 🚀\n- [ ] 🚀 Alpha\n- [ ] Alpha\n## B\n- [ ] Alpha\n- [ ]'
        (self.root / 'board.md').write_text(board, encoding='utf-8')
        cases = [c for c in self.load() if 'lane' in c]
        self.assertEqual([(c['lane'], c['text'], c['raw'], c['element_id']) for c in cases], [
            ('A', 'Alpha', '🚀 Alpha', '🚀 Alpha'),
            ('A', 'Alpha', 'Alpha', 'Alpha'),
            ('B', 'Alpha', 'Alpha', 'Alpha 2'),
        ])

    def test_empty_board_is_one_record(self):
        (self.root / 'board.md').write_text('---\nkanban-plugin: board\n---\n## A\n## B\n', encoding='utf-8')
        self.assertEqual([(c['filename'], c['lanes'], c['text']) for c in self.load()], [('board', ['A', 'B'], 'A\nB')])


class Screen(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name).resolve() / 'board.md'
        self.path.write_text(BOARD, encoding='utf-8')

    def card(self, title):
        case = next(c for c in vault_mod._cards(self.path, read_note(self.path)) if c.get('raw', '').startswith(title))
        case['archive'] = Vault.name
        return case

    def run_case(self, case, commands, edited=None):
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen, 'read_command', side_effect=commands), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen, 'haptic') as hap, \
             mock.patch.object(search_screen, 'error') as err, \
             mock.patch.object(search_screen, '_confirm') as confirm, \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', return_value=edited) as edit, \
             redirect_stdout(io.StringIO()) as out:
            search_screen.open_case([(0, case)], 1, '')
        self.hap, self.err, self.confirm, self.edit = hap, err, confirm, edit
        return out.getvalue()

    def show(self, case):
        with mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch.object(search_screen.archives, 'cases', return_value=[]), \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.keeper, 'configured', return_value=False), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             redirect_stdout(io.StringIO()) as out:
            search_screen.show_case(case)
        return out.getvalue()

    def test_save_card(self):
        case = self.card('Alpha')
        search_screen._save(case, 'Alpha\nAlpha note')
        self.assertEqual(read_note(self.path), _join(LINES[:8], ['- [ ] Alpha', '\tAlpha note'], LINES[9:]))
        self.assertEqual((case['raw'], case['text']), ('Alpha\nAlpha note', 'Alpha\nAlpha note'))

    def test_second_save_after_title_change(self):
        case = self.card('Alpha')
        search_screen._save(case, 'Alpha 2')
        search_screen._save(case, 'Alpha 2\nAlpha note')
        self.assertEqual(read_note(self.path), _join(LINES[:8], ['- [ ] Alpha 2', '\tAlpha note'], LINES[9:]))

    def test_save_refuses_card_changed_on_disk(self):
        case = self.card('Alpha')
        changed = BOARD.replace('- [ ] Alpha', '- [ ] Alpha changed')
        self.path.write_text(changed, encoding='utf-8')
        with self.assertRaises(ValueError):
            search_screen._save(case, 'mine')
        self.assertEqual(read_note(self.path), changed)

    def test_edit_gets_raw(self):
        self.run_case(self.card('Gamma'), ['e', 'b'], edited='Gamma\nGamma note')
        self.edit.assert_called_once_with('Gamma\nGamma note')
        self.assertEqual(read_note(self.path), BOARD)

    def test_empty_edit_rejected(self):
        self.run_case(self.card('Alpha'), ['e', 'b'], edited='  \n')
        self.err.assert_called_once_with('Empty text — edit cancelled')
        self.confirm.assert_not_called()
        self.assertEqual(read_note(self.path), BOARD)

    def test_move(self):
        out = self.run_case(self.card('Alpha'), ['m', '2', 'b'])
        self.assertEqual(read_note(self.path), _join(LINES[:8], LINES[9:18], ['- [x] Alpha'], LINES[18:]))
        self.assertIn(f'{num(1, 1)}{TODO}{dim("  · here")}\n', out)
        self.assertIn(f'{num(2, 1)}{DONE}\n', out)
        self.assertIn(f'{num(4, 1)}{ARCHIVE}\n', out)
        self.hap.assert_called_once_with('success')
        self.err.assert_not_called()

    def test_move_cancelled(self):
        for choice in ('b', '0', '5', 'abc'):
            with self.subTest(choice=choice):
                self.run_case(self.card('Alpha'), ['m', choice, 'b'])
                self.assertEqual(read_note(self.path), BOARD)
                self.hap.assert_not_called()
                self.err.assert_not_called()

    def test_move_same_lane_not_saved(self):
        before = self.path.stat().st_mtime_ns
        self.run_case(self.card('Alpha'), ['m', '1', 'b'])
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.hap.assert_not_called()

    def test_move_refuses_card_changed_on_disk(self):
        case = self.card('Alpha')
        changed = BOARD.replace('- [ ] Alpha', '- [ ] Alpha changed')
        self.path.write_text(changed, encoding='utf-8')
        self.run_case(case, ['m', '2', 'b'])
        self.err.assert_called_once_with('Could not move: the card changed on disk, open it again')
        self.assertEqual(read_note(self.path), changed)

    def test_move_missing_file(self):
        case = self.card('Alpha')
        self.path.unlink()
        self.run_case(case, ['m', 'b'])
        self.assertTrue(self.err.call_args[0][0].startswith('Could not read the board: '))

    def test_add(self):
        self.run_case(self.card('Gamma'), ['a', 'b'], edited='Eta\nEta note\n')
        self.edit.assert_called_once_with('')
        self.assertEqual(read_note(self.path), _join(LINES[:18], ['- [x] Eta', '\tEta note'], LINES[18:]))
        self.hap.assert_called_once_with('success')

    def test_add_empty_does_nothing(self):
        self.run_case(self.card('Alpha'), ['a', 'b'], edited=' \n')
        self.assertEqual(read_note(self.path), BOARD)
        self.err.assert_not_called()

    def test_add_without_editor(self):
        self.run_case(self.card('Alpha'), ['a', 'b'], edited=None)
        self.err.assert_called_once_with('Could not open the editor')
        self.assertEqual(read_note(self.path), BOARD)

    def test_add_failed_save_copies_text(self):
        with mock.patch.object(search_screen, 'save_note', side_effect=OSError('disk full')), \
             mock.patch.object(search_screen, 'copy_text', return_value=True) as copy:
            self.run_case(self.card('Alpha'), ['a', 'b'], edited='Eta')
        copy.assert_called_once_with('Eta')
        self.err.assert_called_once_with('Could not save: disk full — your text is copied')
        self.assertEqual(read_note(self.path), BOARD)

    def test_m_and_a_ignored_on_notes(self):
        note = {'archive': Vault.name, 'filepath': str(self.path), 'filename': 'board', 'text': read_note(self.path)}
        self.run_case(note, ['m', 'a', 'b'])
        self.edit.assert_not_called()
        self.assertEqual(read_note(self.path), BOARD)

    def test_card_markdown_rendered(self):
        text = '**Alpha**\n**Score:** 9'
        case = {'text': text, 'raw': text, 'lane': TODO, 'archive': Vault.name,
                'filepath': str(self.path), 'element_id': '**Alpha**', 'source': 'board.md'}
        out = self.show(case)
        self.assertIn('Alpha', out.splitlines())
        self.assertIn('\033[1mScore:\033[22m 9', out.splitlines())
        self.assertNotIn('**', out)

    def test_board_found_by_name(self):
        results = search_screen.search.search(vault_mod._cards(self.path, BOARD), 'board')
        self.assertEqual([c['filename'] for _, c in results], ['board'])

    def test_board_opens_lists(self):
        board = vault_mod._cards(self.path, BOARD)[0]
        with mock.patch('screens.tree_screen.tree_screen') as tree, \
             mock.patch.object(search_screen, 'show_case') as show:
            self.assertIsNone(search_screen.open_case([(0, board)], 1, ''))
        tree.assert_called_once_with(str(self.path))
        show.assert_not_called()

    def test_card_header_and_nav(self):
        out = self.show(self.card('Alpha'))
        self.assertIn(f'── {TODO} (Vault)', out)
        self.assertIn('[m] move', out)
        self.assertIn('[a] add card', out)


class Links(unittest.TestCase):
    PATH = Path('/v/board.md')

    def numbered(self, text, here=None):
        return wikilinks.numbered(text, vault_mod._cards(self.PATH, BOARD), lambda shown, n: f'{shown}<{n}>', here=here)

    def test_anchor_inside_board(self):
        text, found = self.numbered('[[#Beta]]', here=str(self.PATH))
        self.assertEqual(text, 'Beta<1>')
        self.assertEqual([c['raw'] for c in found[0]], ['Beta'])

    def test_board_link_opens_board_first(self):
        text, found = self.numbered('[[board]]')
        self.assertEqual(text, 'board<1>')
        self.assertEqual(found[0][0]['lanes'], TITLES)




if __name__ == '__main__':
    unittest.main()
