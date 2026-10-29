import io
import unittest
from unittest import mock

from screens import keeper_screen, search_screen
from ui.interface import dim, num, underline

URL = 'https://example.com/alpha'


def _printed(printed):
    return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)


class DimLinks(unittest.TestCase):
    def test_link_underlined_text_stays_dim(self):
        self.assertEqual(search_screen.dim_links(f'see {URL} now'), dim(f'see {underline(URL)} now'))

    def test_no_reset_after_link(self):
        self.assertNotIn('\033[0m now', search_screen.dim_links(f'see {URL} now'))

    def test_several_links(self):
        self.assertEqual(search_screen.dim_links(f'{URL} and {URL}/b'),
                         dim(f'{underline(URL)} and {underline(URL + "/b")}'))

    def test_cyrillic(self):
        self.assertEqual(search_screen.dim_links(f'Альфа {URL}'), dim(f'Альфа {underline(URL)}'))

    def test_without_links(self):
        self.assertEqual(search_screen.dim_links('Alpha'), dim('Alpha'))
        self.assertEqual(search_screen.dim_links(''), dim(''))


class UrlEnd(unittest.TestCase):
    def test_trailing_marks_left_out(self):
        for tail in ('»', '.', ',', ';', ':', '!', '?', '"', "'", '”', '’', '>', ']', '}', '».', '...'):
            with self.subTest(tail=tail):
                self.assertEqual(search_screen.highlight_links(f'{URL}{tail}'),
                                 search_screen.highlight_links(URL) + tail)

    def test_quoted(self):
        self.assertEqual(search_screen.highlight_links(f'«{URL}»'), f'«{dim(underline(URL))}»')

    def test_unbalanced_bracket_left_out(self):
        self.assertEqual(search_screen.highlight_links(f'(see {URL})'), f'(see {dim(underline(URL))})')
        self.assertEqual(search_screen.highlight_links(f'({URL}).'), f'({dim(underline(URL))}).')

    def test_balanced_bracket_kept(self):
        url = 'https://example.com/Alpha_(beta)'
        self.assertEqual(search_screen.highlight_links(url), dim(underline(url)))
        self.assertEqual(search_screen.highlight_links(f'{url}.'), dim(underline(url)) + '.')

    def test_slash_and_query_kept(self):
        for url in (URL + '/', URL + '?a=1&b=2', URL + '#top'):
            with self.subTest(url=url):
                self.assertEqual(search_screen.highlight_links(url), dim(underline(url)))

    def test_cyrillic_sentence(self):
        self.assertEqual(search_screen.highlight_links(f'Смотри {URL}.'), f'Смотри {dim(underline(URL))}.')

    def test_dim_links_same_rule(self):
        self.assertEqual(search_screen.dim_links(f'«{URL}»'), dim(f'«{underline(URL)}»'))

    def test_bare_scheme_is_not_a_link(self):
        self.assertEqual(search_screen.highlight_links('https://'), 'https://')
        self.assertEqual(search_screen.dim_links('see https://'), dim('see https://'))


class Screen(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(keeper_screen, '_width', return_value=200)
        patch.start()
        self.addCleanup(patch.stop)

    def test_aside(self):
        with mock.patch('builtins.print') as printed:
            keeper_screen._aside(f'Based on: «Alpha {URL}»')
        self.assertIn(underline(URL), _printed(printed))
        self.assertTrue(_printed(printed).startswith('\033[2m'))

    def test_source(self):
        with mock.patch('builtins.print') as printed:
            keeper_screen._source(1, {'text': f'Alpha {URL}', 'archive': 'Vault'}, 1)
        self.assertIn(search_screen.highlight_links(URL), _printed(printed))

    def test_record_line(self):
        out = io.StringIO()
        with mock.patch.object(keeper_screen, '_nav'), \
             mock.patch.object(keeper_screen.keeper, 'has_server', return_value=False), \
             mock.patch('sys.stdout', out):
            keeper_screen._draw([], [], {'text': f'Alpha {URL}'}, None, {'slot': 'local'})
        self.assertIn(num(1) + dim(f'Alpha {underline(URL)}'), out.getvalue())
