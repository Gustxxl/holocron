import unittest
from unittest.mock import patch

from screens import search_screen


def _case(text, path):
    return {'text': text, 'filepath': path, 'element_id': 'e'}


class ListOrder(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c = _case('alpha', 'a'), _case('beta', 'b'), _case('gamma', 'c')

    def _order(self, favorites):
        with patch('core.favorites.config.load', return_value={'favorites': favorites}):
            return [case for _, case in search_screen._all([self.c, self.a, self.b])]

    def test_alphabetical_without_pins(self):
        self.assertEqual(self._order([]), [self.a, self.b, self.c])

    def test_pinned_first_in_pin_order(self):
        self.assertEqual(self._order([['c', 'e'], ['b', 'e']]), [self.c, self.b, self.a])

    def test_missing_pin_ignored(self):
        self.assertEqual(self._order([['x', 'e'], ['b', 'e']]), [self.b, self.a, self.c])
