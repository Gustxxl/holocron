import os
import unittest
from unittest import mock

from screens import search_screen
from ui import markdown
from ui.interface import dim
from ui.note import render_note


class IsRule(unittest.TestCase):
    def test_rules(self):
        for line in ('---', '***', '___', '----------', '- - -', '* * *', '   ---', '---   '):
            with self.subTest(line=line):
                self.assertTrue(markdown.is_rule(line))

    def test_not_rules(self):
        for line in ('', '--', '-_-', '    ---', '--- Panel Tool ---', '---x', '— — —', 'Альфа ---'):
            with self.subTest(line=line):
                self.assertFalse(markdown.is_rule(line))


class Rules(unittest.TestCase):
    def test_full_width(self):
        self.assertEqual(markdown.rules('Alpha\n---\nBeta', 10), f'Alpha\n{dim("─" * 10)}\nBeta')

    def test_cyrillic_around(self):
        self.assertEqual(markdown.rules('Альфа\n___\nБета', 5), f'Альфа\n{dim("─" * 5)}\nБета')

    def test_code_kept(self):
        code = markdown.code_blocks('```\n---\n```')
        self.assertEqual(markdown.rules(code, 10), code)

    def test_no_rules(self):
        self.assertEqual(markdown.rules('Alpha\n--- Beta ---', 10), 'Alpha\n--- Beta ---')
        self.assertEqual(markdown.rules('', 10), '')


class Note(unittest.TestCase):
    def test_rule_stretches(self):
        for width in (30, 100):
            with self.subTest(width=width):
                self.assertIn(dim('─' * width), render_note('Alpha\n\n---\n\nBeta', width))

    def test_front_matter_is_not_a_rule(self):
        self.assertEqual(render_note('---\nkey: value\n---\nAlpha', 30), 'Alpha')


class Block(unittest.TestCase):
    def test_board_block(self):
        case = {'text': 'Alpha\n---\nBeta', 'archive': 'Board', 'source': 'board.excalidraw'}
        with mock.patch('shutil.get_terminal_size', return_value=os.terminal_size((41, 24))), \
             mock.patch.object(search_screen.archives, 'cases', return_value=[]), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             mock.patch.object(search_screen.editor, 'available', return_value=False), \
             mock.patch.object(search_screen.keeper, 'configured', return_value=[]), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch('builtins.print') as printed:
            search_screen.show_case(case)
        out = '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)
        self.assertIn(dim('─' * 40), out)
        self.assertNotIn('\n---\n', out)
