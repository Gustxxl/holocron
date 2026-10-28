import os
import unittest
from unittest import mock

from screens import search_screen
from ui import markdown
from ui.interface import dim
from ui.note import render_note


def line(n):
    return dim('─' * n)


class IsRule(unittest.TestCase):
    def test_rules(self):
        for text in ('---', '***', '___', '----------', '- - -', '* * *', '   ---', '---   '):
            with self.subTest(text=text):
                self.assertTrue(markdown.is_rule(text))

    def test_not_rules(self):
        for text in ('', '--', '-_-', '    ---', '--- Panel Tool ---', '---x', '— — —', 'Альфа ---', '|---|'):
            with self.subTest(text=text):
                self.assertFalse(markdown.is_rule(text))


class Rules(unittest.TestCase):
    def test_separator_full_width(self):
        self.assertEqual(markdown.rules('Alpha\n\n---\n\nBeta', 10), f'Alpha\n\n{line(10)}\n\nBeta')

    def test_separator_before_text(self):
        self.assertEqual(markdown.rules('Alpha\n\n---\nBeta', 10), f'Alpha\n\n{line(10)}\nBeta')

    def test_edges_count_as_blank(self):
        self.assertEqual(markdown.rules('---\n\nAlpha\n\n---', 10), f'{line(10)}\n\nAlpha\n\n{line(10)}')
        self.assertEqual(markdown.rules('---', 10), line(10))
        self.assertEqual(markdown.rules('---\nAlpha', 10), f'{line(10)}\nAlpha')

    def test_spaces_count_as_blank(self):
        self.assertEqual(markdown.rules('Alpha\n   \n---\n \nBeta', 10), f'Alpha\n   \n{line(10)}\n \nBeta')

    def test_under_text_keeps_length(self):
        self.assertEqual(markdown.rules('Alpha\n-----\nBeta', 10), f'Alpha\n{line(5)}\nBeta')
        self.assertEqual(markdown.rules('Alpha\n---\n\nBeta', 10), f'Alpha\n{line(3)}\n\nBeta')

    def test_frame_capped_by_width(self):
        self.assertEqual(markdown.rules('Alpha\n' + '-' * 30 + '\nBeta', 10), f'Alpha\n{line(10)}\nBeta')

    def test_spaced_and_indented(self):
        self.assertEqual(markdown.rules('Alpha\n  - - -\nBeta', 10), f'Alpha\n{line(5)}\nBeta')

    def test_error_window(self):
        text = 'Alpha.\n\n---\nBeta:\n-----\nTool\n-----\nGamma.\n\n-----\nOK\n-----'
        self.assertEqual(markdown.rules(text, 40),
                         f'Alpha.\n\n{line(40)}\nBeta:\n{line(5)}\nTool\n{line(5)}\nGamma.\n\n{line(5)}\nOK\n{line(5)}')

    def test_box_around_several_lines(self):
        self.assertEqual(markdown.rules('-----\nAlpha\nBeta\n-----', 40), f'{line(5)}\nAlpha\nBeta\n{line(5)}')

    def test_twin_after_blank_line_is_not_a_pair(self):
        self.assertEqual(markdown.rules('A\n\n---\n\nB\n\n---\n\nC', 10), f'A\n\n{line(10)}\n\nB\n\n{line(10)}\n\nC')

    def test_twin_of_other_kind_is_not_a_pair(self):
        self.assertEqual(markdown.rules('---\nAlpha\n***', 10), f'{line(10)}\nAlpha\n{line(3)}')

    def test_adjacent_rules_are_frames(self):
        self.assertEqual(markdown.rules('---\n---', 10), f'{line(3)}\n{line(3)}')

    def test_cyrillic_around(self):
        self.assertEqual(markdown.rules('Альфа\n\n___\n\nБета', 5), f'Альфа\n\n{line(5)}\n\nБета')

    def test_code_kept(self):
        code = markdown.code_blocks('```\n---\n```')
        self.assertEqual(markdown.rules(code, 10), code)

    def test_no_rules(self):
        self.assertEqual(markdown.rules('Alpha\n--- Beta ---', 10), 'Alpha\n--- Beta ---')
        self.assertEqual(markdown.rules('', 10), '')


class Note(unittest.TestCase):
    def test_separator_stretches(self):
        for width in (30, 100):
            with self.subTest(width=width):
                self.assertEqual(render_note('Alpha\n\n---\n\nBeta', width), f'Alpha\n\n{line(width)}\n\nBeta')

    def test_under_text(self):
        self.assertEqual(render_note('Alpha\n---\nBeta', 100), f'Alpha\n{line(3)}\nBeta')

    def test_spaced_rule_is_not_a_bullet(self):
        out = render_note('Alpha\n\n- - -\n\nBeta', 20)
        self.assertEqual(out, f'Alpha\n\n{line(20)}\n\nBeta')
        self.assertNotIn('•', out)

    def test_code_kept(self):
        self.assertNotIn('─', render_note('```\n---\n```', 20))

    def test_front_matter_is_not_a_rule(self):
        self.assertEqual(render_note('---\nkey: value\n---\nAlpha', 30), 'Alpha')


class Block(unittest.TestCase):
    def show(self, text):
        case = {'text': text, 'archive': 'Board', 'source': 'board.excalidraw'}
        with mock.patch('shutil.get_terminal_size', return_value=os.terminal_size((41, 24))), \
             mock.patch.object(search_screen.archives, 'cases', return_value=[]), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             mock.patch.object(search_screen.editor, 'available', return_value=False), \
             mock.patch.object(search_screen.keeper, 'configured', return_value=[]), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch('builtins.print') as printed:
            search_screen.show_case(case)
        return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)

    def test_separator(self):
        out = self.show('Alpha\nOne\n\n---\n\nTwo')
        self.assertIn(line(40), out)
        self.assertNotIn('---', out)

    def test_error_window(self):
        out = self.show('Alpha\n-----\nTool\n-----\nOK')
        self.assertIn(f'{line(5)}\nTool\n{line(5)}\nOK', out)
        self.assertNotIn(line(40), out)

    def test_separator_above_error_window(self):
        out = self.show('Alpha\nOne.\n\n---\nTwo:\n-----\nTool\n-----')
        self.assertIn(f'{line(40)}\nTwo:\n{line(5)}\nTool\n{line(5)}', out)
