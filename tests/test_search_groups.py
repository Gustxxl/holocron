import io
import os
import re
import unittest
from contextlib import redirect_stdout
from unittest import mock

from core import settings
from screens import search_screen

_ANSI = re.compile(r'\x1b\[[0-9;]*m')


def _cases(name, n):
    return [{'text': f'{name} record {i}'} for i in range(n)]


def _scored(cases, exact):
    return [(10 if i < exact else 1, c) for i, c in enumerate(cases)]


class Grouped(unittest.TestCase):
    def setUp(self):
        self.a, self.b = _cases('alpha', 11), _cases('beta', 4)
        patches = [
            mock.patch.object(search_screen, 'search_separator', return_value=';'),
            mock.patch.object(search_screen.search, 'is_exact', side_effect=lambda s: s >= 10),
            mock.patch.object(search_screen, 'clear_screen'),
            mock.patch.object(search_screen.shutil, 'get_terminal_size', return_value=os.terminal_size((100, 40))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _find(self, a_exact=11, b_exact=4):
        groups = [_scored(self.a, a_exact), _scored(self.b, b_exact)]
        with mock.patch.object(search_screen.search, 'search_many', return_value=(groups, [])):
            return search_screen._find([], 'alpha; beta')

    def _page(self, results, groups, page):
        out = io.StringIO()
        with redirect_stdout(out):
            search_screen.show_list(results, page, 'alpha; beta', groups=groups)
        return [ln.strip() for ln in _ANSI.sub('', out.getvalue()).splitlines() if ln.strip()]

    def test_nothing_lost(self):
        results, _ = self._find()
        self.assertEqual(len(results), 15)
        self.assertEqual({id(c) for _, c in results}, {id(c) for c in self.a + self.b})

    def test_every_group_on_first_page(self):
        results, _ = self._find()
        first = [c for _, c in results[:search_screen.PAGE]]
        self.assertEqual(sum(c in self.b for c in first), 4)
        self.assertTrue(any(c in self.a for c in first))

    def test_headers(self):
        results, groups = self._find()
        one, two = self._page(results, groups, 0), self._page(results, groups, 1)
        self.assertEqual(sum(ln.startswith('alpha ·') for ln in one), 2)
        self.assertEqual(sum(ln.startswith('beta ·') for ln in one), 1)
        self.assertTrue(two[1].startswith('alpha ·'))

    def test_similar_in_continuation(self):
        results, groups = self._find(a_exact=7)
        self.assertNotIn('Similar', self._page(results, groups, 0))
        two = self._page(results, groups, 1)
        self.assertEqual(two[two.index('Similar') + 1].split(' ', 1)[1], 'alpha record 7')

    def test_similar_under_header_without_exact(self):
        results, groups = self._find(b_exact=0)
        one = self._page(results, groups, 0)
        self.assertEqual(one[one.index(next(ln for ln in one if ln.startswith('beta ·'))) + 1], 'Similar')

    def test_single_query_is_plain(self):
        with mock.patch.object(search_screen.search, 'search', return_value=[(10, self.a[0])]):
            results, groups = search_screen._find([], 'alpha')
        self.assertIsNone(groups)
        self.assertEqual(len(results), 1)

    def test_short_parts_dropped(self):
        self.assertEqual(search_screen._parts('ab; nginx'), ['nginx'])


class Highlight(unittest.TestCase):
    def test_every_query_marked(self):
        out = search_screen.highlight('nginx down, ERR504 again', 'nginx', 'ERR504')
        self.assertIn(search_screen._MARK + 'nginx', out)
        self.assertIn(search_screen._MARK + 'ERR504', out)


class Separator(unittest.TestCase):
    def _sep(self, cfg):
        with mock.patch.object(settings, 'load', return_value=cfg):
            return settings.search_separator()

    def test_default(self):
        self.assertEqual(self._sep({}), ';')

    def test_off(self):
        self.assertEqual(self._sep({'search_separator': ''}), '')

    def test_custom(self):
        self.assertEqual(self._sep({'search_separator': '|'}), '|')

    def test_broken_value(self):
        self.assertEqual(self._sep({'search_separator': 5}), ';')


if __name__ == '__main__':
    unittest.main()
