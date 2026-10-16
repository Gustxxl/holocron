import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest import mock
from unittest.mock import patch

from screens import search_screen
from screens.search_screen import _wrap, first_line, highlight, highlight_links
from screens.tasks_screen import _card
from ui.clean_path import clean_input_path
from ui.interface import nav_line


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

    def test_part_of_underscored_name(self):
        result = highlight('XY_AB12 - z', 'AB12')
        self.assertIn(f'{search_screen._HL}AB12{search_screen._RESET}', result)

    def test_underscore_and_space_same_phrase(self):
        for query in ('AB12 CD', 'AB12_CD'):
            with self.subTest(query=query):
                result = highlight('AB12_CD - x', query)
                self.assertIn(f'{search_screen._MARK}AB12_CD{search_screen._RESET}', result)

    def test_phrase_not_inside_longer_name(self):
        self.assertNotIn(search_screen._MARK, highlight('AB12_CD_EF', 'AB12 CD'))

    def test_phrase_with_ye(self):
        for query in ('ЛЕС_ДОМ', 'лёс дом'):
            with self.subTest(query=query):
                result = highlight('ЛЕС_ДОМ - x', query)
                self.assertIn(f'{search_screen._MARK}ЛЕС_ДОМ{search_screen._RESET}', result)


class HighlightLinks(unittest.TestCase):
    def test_dims_url(self):
        result = highlight_links('see https://example.com here')
        self.assertIn('\033[2m', result)
        self.assertIn('https://example.com', result)

    def test_no_url(self):
        self.assertEqual(highlight_links('no links here'), 'no links here')

    def test_keeps_fragment(self):
        url = 'https://366.abc.ru/gg/operator/#uuid:serviceCall$12345'
        self.assertIn(url, highlight_links(f'Заявка: {url}'))


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


class NavLine(unittest.TestCase):
    ITEMS = [('e', 'edit'), ('j number', 'jump', 'j#', 'jump'), ('b', 'back')]
    FULL = '  [e] edit   [j number] jump   [b] back'
    SHORT = '  e edit · j# jump · b back'
    KEYS = '  e j# b'

    def test_full_when_fits(self):
        self.assertEqual(nav_line(self.ITEMS, len(self.FULL)), self.FULL)

    def test_short_when_full_too_long(self):
        self.assertEqual(nav_line(self.ITEMS, len(self.FULL) - 1), self.SHORT)

    def test_short_at_exact_width(self):
        self.assertEqual(nav_line(self.ITEMS, len(self.SHORT)), self.SHORT)

    def test_keys_only_when_short_too_long(self):
        self.assertEqual(nav_line(self.ITEMS, len(self.SHORT) - 1), self.KEYS)

    def test_pair_uses_same_short_form(self):
        self.assertEqual(nav_line([('b', 'back')], 5), '  b')
        self.assertEqual(nav_line([('b', 'back')], 80), '  [b] back')

    def test_default_width_from_terminal(self):
        size = os.terminal_size((len(self.SHORT) + 1, 24))
        with mock.patch('ui.interface.shutil.get_terminal_size', return_value=size):
            self.assertEqual(nav_line(self.ITEMS), self.SHORT)


class TaskCardNav(unittest.TestCase):
    NOW = datetime(2026, 10, 15, 12, 0)
    TASK = {'title': 'Buy cable', 'list_name': 'Work', 'due': None, 'all_day': False,
            'notes': '', 'place': ''}

    def _nav(self, **fields):
        task = {**self.TASK, **fields}
        return [ln for ln in _card(task, 1, 2, self.NOW, []) if 'back' in ln]

    def test_nav_without_notes(self):
        self.assertEqual(len(self._nav()), 1)

    def test_nav_with_notes(self):
        self.assertEqual(len(self._nav(notes='USB-C')), 1)


class SearchList(unittest.TestCase):
    def test_hint_not_raw(self):
        case = {'text': 'Case one', 'source': 'a.md'}
        with patch.object(search_screen, 'clear_screen'), \
             redirect_stdout(io.StringIO()) as out:
            search_screen.show_list([(0, case)], 0, 'case')
        self.assertNotIn("[('", out.getvalue())
