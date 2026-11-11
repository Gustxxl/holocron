import unittest

from screens.search_screen import highlight_links
from ui.interface import bold, dim, italic, underline
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


if __name__ == '__main__':
    unittest.main()
