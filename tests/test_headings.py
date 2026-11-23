import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from screens import search_screen
from screens.search_screen import by_name, first_line, highlight_links
from ui.interface import bold, dim, italic, underline, visible
from ui.markdown import code_blocks
from ui.note import render_note


def rule(n):
    return dim('─' * n)


class Levels(unittest.TestCase):
    def test_each_level(self):
        for marks in ('#', '##'):
            with self.subTest(marks=marks):
                self.assertEqual(render_note(f'{marks} Alpha', 80), f'{bold("Alpha")}\n{rule(5)}')
        self.assertEqual(render_note('### Alpha', 80), bold('Alpha'))
        for marks in ('####', '#####', '######'):
            with self.subTest(marks=marks):
                self.assertEqual(render_note(f'{marks} Alpha', 80), bold(italic('Alpha')))

    def test_closing_marks_dropped(self):
        self.assertEqual(render_note('### Alpha ###', 80), bold('Alpha'))

    def test_markdown_inside(self):
        self.assertEqual(render_note('### **Alpha** [[Beta]]', 80), bold('Alpha Beta'))

    def test_tag_is_not_heading(self):
        self.assertEqual(render_note('#Alpha', 80), '#Alpha')

    def test_empty_heading(self):
        self.assertEqual(render_note('Alpha\n#  \nBeta', 80), 'Alpha\n\nBeta')


class Rule(unittest.TestCase):
    def test_follows_longest_row(self):
        text = 'Alpha Beta\nGamma'
        self.assertEqual(render_note('# Alpha Beta Gamma', 11), f'{bold(text)}\n{rule(10)}')

    def test_capped_by_width(self):
        word = 'A' * 30
        self.assertEqual(render_note(f'# {word}', 10), f'{bold(word)}\n{rule(10)}')


class Spacing(unittest.TestCase):
    def test_blank_line_before(self):
        self.assertEqual(render_note('Alpha\n### Beta\nGamma', 80), f'Alpha\n\n{bold("Beta")}\nGamma')

    def test_no_double_blank(self):
        self.assertEqual(render_note('Alpha\n\n### Beta', 80), f'Alpha\n\n{bold("Beta")}')

    def test_no_blank_at_top(self):
        self.assertEqual(render_note('### Beta\nGamma', 80), f'{bold("Beta")}\nGamma')

    def test_heading_after_heading(self):
        self.assertEqual(render_note('# Alpha\n## Beta', 80), f'{bold("Alpha")}\n{rule(5)}\n\n{bold("Beta")}\n{rule(4)}')


class Links(unittest.TestCase):
    def test_deep_heading_keeps_style_after_link(self):
        out = highlight_links(render_note('#### Alpha https://x.io Beta', 80))
        link = dim(underline('https://x.io'))
        self.assertEqual(out, f'\033[1m\033[3mAlpha {link}\033[1m\033[3m Beta\033[23m\033[0m')


class BlockBody(unittest.TestCase):
    def _wrap(self, text):
        return search_screen._wrap(text, 80)

    def test_blank_line_before(self):
        self.assertEqual(self._wrap('Alpha\n### Beta\nGamma'), f'Alpha\n\n{bold("Beta")}\nGamma')

    def test_no_blank_at_top(self):
        self.assertEqual(self._wrap('### Beta\nGamma'), f'{bold("Beta")}\nGamma')

    def test_no_double_blank(self):
        self.assertEqual(self._wrap('Alpha\n\n### Beta'), f'Alpha\n\n{bold("Beta")}')

    def test_rule_under_big_heading(self):
        self.assertEqual(self._wrap('## Альфа'), f'{bold("Альфа")}\n{rule(5)}')

    def test_tag_is_not_heading(self):
        self.assertEqual(self._wrap('#Alpha'), '#Alpha')

    def test_code_and_tables_untouched(self):
        for text in (code_blocks('```\n### Alpha\n```'), '| ### Alpha | Beta |'):
            with self.subTest(text=text):
                self.assertEqual(self._wrap(text), text)


class BlockTitle(unittest.TestCase):
    def test_marks_dropped(self):
        for text in ('### Alpha\nBeta', '\n  ## Alpha  \nBeta', '# Alpha #'):
            with self.subTest(text=text):
                self.assertEqual(first_line({'text': text}), 'Alpha')

    def test_card(self):
        self.assertEqual(first_line({'text': '### **Alpha**', 'lane': 'Todo'}), 'Alpha')

    def test_note_keeps_its_name(self):
        self.assertEqual(first_line({'text': '# Beta', 'filename': 'Alpha'}), 'Alpha')

    def test_tag_kept(self):
        self.assertEqual(first_line({'text': '#Alpha'}), '#Alpha')

    def test_sorted_by_text(self):
        cases = [{'text': '### Beta'}, {'text': 'Alpha'}]
        self.assertEqual([first_line(c) for c in by_name(cases)], ['Alpha', 'Beta'])


class BlockCard(unittest.TestCase):
    def _shown(self, text):
        case = {'text': text, 'source': 'Board.excalidraw.md', 'archive': 'Board'}
        out = io.StringIO()
        with mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch.object(search_screen.archives, 'cases', return_value=[]), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             mock.patch.object(search_screen.editor, 'available', return_value=False), \
             mock.patch.object(search_screen.keeper, 'configured', return_value=False), \
             mock.patch('shutil.get_terminal_size', return_value=os.terminal_size((81, 24))), \
             redirect_stdout(out):
            search_screen.show_case(case)
        return visible(out.getvalue())

    def test_title_without_marks(self):
        out = self._shown('### Alpha\nBeta')
        self.assertNotIn('###', out)
        self.assertIn('\nAlpha\n\nBeta\n', out)

    def test_heading_in_body(self):
        out = self._shown('Alpha\n## Beta\nGamma')
        self.assertIn('\nBeta\n────\nGamma\n', out)
        self.assertNotIn('##', out)


class BlockSave(unittest.TestCase):
    def test_editor_gets_marks(self):
        case = {'text': 'Alpha', 'raw': '### Alpha', 'filepath': '/Альфа/Board.excalidraw', 'element_id': 'A1'}
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen, 'read_command', side_effect=['e', 'b']), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', return_value='### Alpha') as edit:
            search_screen.open_case([(0, case)], 1, '')
        edit.assert_called_once_with('### Alpha')


if __name__ == '__main__':
    unittest.main()
