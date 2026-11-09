import unittest

from screens import search_screen
from screens.search_screen import highlight
from ui import markdown
from ui.interface import bold, dim
from ui.note import render_note

MARK, MARK_OFF = search_screen._MARK, search_screen._MARK_OFF
HL, HL_OFF = search_screen._HL, search_screen._HL_OFF
BG = markdown._CODE_BG


class Bold(unittest.TestCase):
    def test_heading_stays_bold_after_match(self):
        out = highlight(render_note('# Alpha Beta Gamma', 80), 'Beta')
        self.assertEqual(out, f'\033[1mAlpha {MARK}Beta{MARK_OFF} Gamma\033[0m')

    def test_inline_bold_stays_bold_after_match(self):
        out = highlight(render_note('Alpha **Beta Gamma Delta** Epsilon', 80), 'Gamma')
        self.assertEqual(out, f'Alpha \033[1mBeta {MARK}Gamma{MARK_OFF} Delta\033[22m Epsilon')

    def test_several_matches_keep_one_reset(self):
        out = highlight(bold('Alpha Beta Gamma'), 'Beta', 'Gamma')
        self.assertEqual(out, f'\033[1mAlpha {MARK}Beta{MARK_OFF} {MARK}Gamma{MARK_OFF}\033[0m')

    def test_word_match_stays_bold(self):
        out = highlight(bold('XY_Alpha Beta'), 'Alpha')
        self.assertEqual(out, f'\033[1mXY_{HL}Alpha{HL_OFF} Beta\033[0m')

    def test_cyrillic(self):
        out = highlight(render_note('# Альфа Бета Гамма', 80), 'Бета')
        self.assertEqual(out, f'\033[1mАльфа {MARK}Бета{MARK_OFF} Гамма\033[0m')

    def test_no_match_unchanged(self):
        self.assertEqual(highlight(bold('Alpha Beta'), 'Omega'), bold('Alpha Beta'))


class FirstWord(unittest.TestCase):
    def test_heading(self):
        out = highlight(render_note('# Alpha Beta', 80), 'Alpha')
        self.assertEqual(out, f'\033[1m{MARK}Alpha{MARK_OFF} Beta\033[0m')

    def test_inline_bold(self):
        out = highlight(render_note('Run **Alpha Beta** now', 80), 'Alpha')
        self.assertEqual(out, f'Run \033[1m{MARK}Alpha{MARK_OFF} Beta\033[22m now')

    def test_word_after_code(self):
        out = highlight(bold('Alpha_XY'), 'Alpha')
        self.assertEqual(out, f'\033[1m{HL}Alpha{HL_OFF}_XY\033[0m')

    def test_dim(self):
        self.assertEqual(highlight(dim('Alpha'), 'Alpha'), f'\033[2m{MARK}Alpha{MARK_OFF}\033[0m')

    def test_cyrillic(self):
        out = highlight(render_note('# Альфа Бета', 80), 'Альфа')
        self.assertEqual(out, f'\033[1m{MARK}Альфа{MARK_OFF} Бета\033[0m')


class Code(unittest.TestCase):
    def test_phrase_keeps_background(self):
        out = markdown.paint_code(highlight(markdown.code_blocks('```\nAlpha Beta\n```'), 'Beta'))
        self.assertEqual(out, f'{BG}Alpha {MARK}Beta{MARK_OFF}{BG}\033[K\033[0m')

    def test_word_keeps_background(self):
        out = markdown.paint_code(highlight(markdown.code_blocks('```\nXY_Alpha\n```'), 'Alpha'))
        self.assertEqual(out, f'{BG}XY_{HL}Alpha{HL_OFF}\033[K\033[0m')
