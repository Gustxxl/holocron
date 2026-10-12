import unittest

from screens.search_screen import _wrap, first_line, highlight, highlight_links
from ui.clean_path import clean_input_path
import os


class Highlight(unittest.TestCase):
    def test_highlights_match(self):
        result = highlight('hello world', 'hello')
        self.assertIn('\033[', result)
        self.assertIn('hello', result)

    def test_no_match_unchanged(self):
        self.assertEqual(highlight('hello world', 'xyz'), 'hello world')

    def test_empty_query(self):
        self.assertEqual(highlight('hello world', ''), 'hello world')

    def test_cyrillic(self):
        self.assertIn('\033[', highlight('привет мир', 'привет'))


class HighlightLinks(unittest.TestCase):
    def test_dims_url(self):
        result = highlight_links('see https://example.com here')
        self.assertIn('\033[2m', result)
        self.assertIn('https://example.com', result)

    def test_no_url(self):
        self.assertEqual(highlight_links('no links here'), 'no links here')


class FirstLine(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(first_line({'text': 'hello\nworld'}), 'hello')

    def test_empty_first_line(self):
        self.assertEqual(first_line({'text': '\nhello'}), 'hello')

    def test_empty_text(self):
        self.assertEqual(first_line({'text': ''}), '(empty)')

    def test_whitespace_only(self):
        self.assertEqual(first_line({'text': '   \n   '}), '(empty)')


class CleanPath(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(clean_input_path('/Users/test/file.md'), os.path.normpath('/Users/test/file.md'))

    def test_strips_quotes(self):
        result = clean_input_path('"~/file.md"')
        self.assertFalse(result.startswith('"'))
        self.assertNotIn('~', result)

    def test_empty(self):
        self.assertEqual(clean_input_path(''), '')

    def test_tilde(self):
        self.assertNotIn('~', clean_input_path('~/test'))


class LongLinks(unittest.TestCase):
    URL = 'https://example.com/docs/some-long-section/another-part/?ref=%2Fa%2Fb%2Fc-d%2Fe-f'

    def test_url_stays_whole(self):
        self.assertIn(self.URL, _wrap(f'See {self.URL} for details', 40).splitlines())

    def test_hyphenated_words_not_split(self):
        out = _wrap('word ' * 6 + 'one-two-three-four end', 20)
        self.assertTrue(any('one-two-three-four' in ln for ln in out.splitlines()))
