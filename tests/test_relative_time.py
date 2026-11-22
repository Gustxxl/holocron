import unittest
from datetime import datetime

from core import dates, events, tasks

NOW = datetime(2026, 11, 22, 23, 58, 40)
LISTS = [{'id': 'L1', 'title': 'Work'}]


class After(unittest.TestCase):
    def test_forms(self):
        for text, expected in (('+5', datetime(2026, 11, 23, 0, 3)), ('+5m', datetime(2026, 11, 23, 0, 3)),
                               ('+2h', datetime(2026, 11, 23, 1, 58)), ('+1h30', datetime(2026, 11, 23, 1, 28)),
                               ('+90', datetime(2026, 11, 23, 1, 28))):
            with self.subTest(text):
                self.assertEqual(dates.after(text, NOW), expected)

    def test_not_relative(self):
        for text in ('5', '+0', '+1h75', '+', '14:30', '+5x', '+1234'):
            with self.subTest(text):
                self.assertIsNone(dates.after(text, NOW))


class Reminder(unittest.TestCase):
    def _parse(self, text):
        return tasks.parse_add(text, LISTS, 'L1', now=NOW)

    def test_in_five_minutes(self):
        draft, problem = self._parse('Включить алерты +5')
        self.assertIsNone(problem)
        self.assertEqual((draft['title'], draft['due']), ('Включить алерты', datetime(2026, 11, 23, 0, 3)))

    def test_number_in_title_stays(self):
        draft, _ = self._parse('Купить 5 яиц')
        self.assertEqual((draft['title'], draft['due']), ('Купить 5 яиц', None))

    def test_with_date_refused(self):
        self.assertEqual(self._parse('Alpha +5 tomorrow'), (None, dates.BOTH))

    def test_bad_amount_named(self):
        self.assertEqual(self._parse('Alpha +1h75'), (None, 'No such time: +1h75'))

    def test_clock_time_still_works(self):
        draft, _ = self._parse('Alpha 14:30')
        self.assertEqual(draft['due'], datetime(2026, 11, 22, 14, 30))


class Event(unittest.TestCase):
    def test_in_fifteen_minutes(self):
        draft, problem = events.parse_add('Созвон +15', LISTS, 'L1', now=NOW)
        self.assertIsNone(problem)
        self.assertEqual((draft['start'], draft['end']), (datetime(2026, 11, 23, 0, 13), datetime(2026, 11, 23, 1, 13)))

    def test_with_date_refused(self):
        self.assertEqual(events.parse_add('Alpha +15 tomorrow', LISTS, 'L1', now=NOW), (None, dates.BOTH))
