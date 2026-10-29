import unittest
from unittest import mock

from screens import keeper_screen
from screens.search_screen import highlight_links
from ui import interface, markdown

URL = 'https://example.com/' + 'a' * 30


class Fill(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(interface.fill('alpha beta gamma', 12, '  '), '  alpha beta\n  gamma')

    def test_long_link_unindented(self):
        self.assertEqual(interface.fill(f'see {URL} now', 20, '  '), f'  see\n{URL}\n  now')

    def test_link_that_fits_keeps_indent(self):
        self.assertEqual(interface.fill('see https://e.co/abc', 20, '  '), '  see\n  https://e.co/abc')

    def test_exact_width_keeps_indent(self):
        self.assertEqual(interface.fill('x' * 18, 20, '  '), '  ' + 'x' * 18)
        self.assertEqual(interface.fill('x' * 19, 20, '  '), 'x' * 19)

    def test_quote_bar(self):
        self.assertEqual(interface.fill(f'see {URL}', 20, '  │ '), f'  │ see\n{URL}')

    def test_cyrillic(self):
        self.assertEqual(interface.fill('альфа бета гамма', 12, '  '), '  альфа бета\n  гамма')

    def test_wide_characters(self):
        self.assertEqual(interface.fill('界' * 9, 20, '  '), '  ' + '界' * 9)
        self.assertEqual(interface.fill('界' * 10, 20, '  '), '界' * 10)

    def test_empty(self):
        self.assertEqual(interface.fill('', 20, '  '), '')
        self.assertEqual(interface.fill('alpha', 20), 'alpha')


class Say(unittest.TestCase):
    def say(self, text, width=20):
        with mock.patch.object(keeper_screen, '_width', return_value=width), \
             mock.patch('builtins.print') as printed:
            keeper_screen._say(text)
        return printed.call_args.args[0]

    def test_long_link_whole(self):
        self.assertEqual(self.say(f'see {URL}'), f'  see\n{highlight_links(URL)}')

    def test_code_block(self):
        code = markdown.paint_code(markdown.code_blocks('```\nSELECT 1\n```'))
        self.assertEqual(self.say('Run this:\n```sql\nSELECT 1\n```'), f'  Run this:\n{code}')

    def test_long_code_line_not_wrapped(self):
        out = self.say('```\n' + 'SELECT alpha, beta, gamma FROM delta' + '\n```')
        self.assertEqual(out.count('\n'), 0)
        self.assertNotIn('```', out)

    def test_quote_keeps_link(self):
        with mock.patch.object(keeper_screen, '_width', return_value=20), \
             mock.patch('builtins.print') as printed:
            keeper_screen._quote(f'see {URL}', '')
        self.assertEqual(printed.call_args.args[0], f'  │ see\n{highlight_links(URL)}')
