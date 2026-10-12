import copy
import unittest
from unittest.mock import patch

from core import waypoints

HOME = {'address': 'Main 1', 'radius': 100, 'proximity': 'arriving'}


class Store(unittest.TestCase):
    def setUp(self):
        self.store = {}
        load = patch.object(waypoints.config, 'load', side_effect=lambda: copy.deepcopy(self.store))
        save = patch.object(waypoints.config, 'save', side_effect=self._save)
        load.start()
        save.start()
        self.addCleanup(load.stop)
        self.addCleanup(save.stop)

    def _save(self, cfg):
        self.store.clear()
        self.store.update(copy.deepcopy(cfg))

    def test_legacy_string_and_garbage(self):
        self.store = {'reminder_locations': {
            'Дом': 'Mileševska 25', 'bad': 5, 'two words': 'x', 'empty': '  ',
            'w': {'address': ' A   1 ', 'radius': 'x', 'proximity': 'z'},
        }}
        self.assertEqual(waypoints.load(), {
            'w': {'address': 'A 1', 'radius': 100, 'proximity': 'arriving'},
            'дом': {'address': 'Mileševska 25', 'radius': 100, 'proximity': 'arriving'},
        })

    def test_not_a_dict(self):
        self.store = {'reminder_locations': []}
        self.assertEqual(waypoints.load(), {})

    def test_put_keeps_trigger(self):
        waypoints.put('home', 'A')
        waypoints.change('home', radius=50, proximity='leaving')
        waypoints.put('@Home', ' B ')
        self.assertEqual(waypoints.load(), {'home': {'address': 'B', 'radius': 50, 'proximity': 'leaving'}})

    def test_put_rejects(self):
        self.assertFalse(waypoints.put('two words', 'A'))
        self.assertFalse(waypoints.put('x', '  '))
        self.assertEqual(waypoints.load(), {})

    def test_rename(self):
        waypoints.put('a', 'A')
        waypoints.put('b', 'B')
        self.assertFalse(waypoints.rename('a', 'b'))
        self.assertTrue(waypoints.rename('a', 'c'))
        self.assertEqual(list(waypoints.load()), ['b', 'c'])

    def test_remove(self):
        waypoints.put('a', 'A')
        self.assertTrue(waypoints.remove('A'))
        self.assertFalse(waypoints.remove('a'))

    def test_keeps_other_config(self):
        self.store = {'operator_name': 'me'}
        waypoints.put('a', 'A')
        self.assertEqual(self.store['operator_name'], 'me')


class Parse(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(waypoints.valid('@Work'))
        self.assertTrue(waypoints.valid('дом'))
        self.assertFalse(waypoints.valid('two words'))
        self.assertFalse(waypoints.valid('w-k'))
        self.assertFalse(waypoints.valid(''))

    def test_edit(self):
        self.assertEqual(waypoints.parse_edit('Home\nMain  1\n'), ('home', 'Main 1', None))
        self.assertEqual(waypoints.parse_edit('home')[2], 'Name on the first line, address below')
        self.assertEqual(waypoints.parse_edit('w-k\nMain 1')[2], 'Name must be one word')


class Linked(unittest.TestCase):
    POINTS = {'home': HOME, 'work': {'address': 'Office', 'radius': 100, 'proximity': 'arriving'}}

    def test_find(self):
        self.assertEqual(waypoints.find(self.POINTS, ' MAIN  1 '), 'home')
        self.assertIsNone(waypoints.find(self.POINTS, ''))

    def test_linked(self):
        items = [
            {'title': 'a', 'place': 'main 1', 'done': False},
            {'title': 'b', 'place': '', 'done': False},
            {'title': 'c', 'place': 'Main 1', 'done': True},
            {'title': 'd', 'place': 'Elsewhere', 'done': False},
        ]
        self.assertEqual(waypoints.linked(items, self.POINTS), {'home': [items[0]], 'work': []})
