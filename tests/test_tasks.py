import unittest
from datetime import datetime

from core import tasks

NOW = datetime(2026, 10, 11, 15, 0)


def _task(id, list='L1', due=None, all_day=False, done=False):
    return {'id': id, 'title': id, 'due': due, 'all_day': all_day, 'list': list, 'done': done}


class Overdue(unittest.TestCase):
    def test_timed(self):
        self.assertTrue(tasks.is_overdue(_task('a', due=datetime(2026, 10, 11, 14)), NOW))
        self.assertFalse(tasks.is_overdue(_task('a', due=datetime(2026, 10, 11, 16)), NOW))

    def test_all_day(self):
        self.assertFalse(tasks.is_overdue(_task('a', due=datetime(2026, 10, 11), all_day=True), NOW))
        self.assertTrue(tasks.is_overdue(_task('a', due=datetime(2026, 10, 10), all_day=True), NOW))

    def test_no_due(self):
        self.assertFalse(tasks.is_overdue(_task('a'), NOW))


class Group(unittest.TestCase):
    LISTS = [{'id': 'L1', 'title': 'Personal'}, {'id': 'L2', 'title': 'Home'}, {'id': 'L3', 'title': 'Off'}]

    def test_order_and_filter(self):
        items = [
            _task('none1'),
            _task('later', due=datetime(2026, 10, 20)),
            _task('done', due=datetime(2026, 10, 1), done=True),
            _task('soon', due=datetime(2026, 10, 12)),
            _task('none2'),
            _task('home', list='L2'),
            _task('hidden', list='L3'),
        ]
        groups = tasks.group(items, self.LISTS, ['L2', 'L1'])
        self.assertEqual([title for title, _ in groups], ['Personal', 'Home'])
        self.assertEqual([t['id'] for t in groups[0][1]], ['soon', 'later', 'none1', 'none2'])
        self.assertEqual([t['id'] for t in groups[1][1]], ['home'])

    def test_empty_selected_list_kept(self):
        self.assertEqual(tasks.group([], self.LISTS, ['L3']), [('Off', [])])

    def test_missing_list_dropped(self):
        self.assertEqual(tasks.group([], self.LISTS, ['gone']), [])


class Upcoming(unittest.TestCase):
    def test_order(self):
        items = [
            _task('none_l2', list='L2'),
            _task('later', due=datetime(2026, 10, 20)),
            _task('none_l1'),
            _task('overdue', list='L2', due=datetime(2026, 10, 9)),
            _task('soon', due=datetime(2026, 10, 12)),
        ]
        shown, rest = tasks.upcoming(items, ['L1', 'L2'], limit=10)
        self.assertEqual([t['id'] for t in shown], ['overdue', 'soon', 'later', 'none_l1', 'none_l2'])
        self.assertEqual(rest, 0)

    def test_limit_and_rest(self):
        items = [_task(str(i), due=datetime(2026, 10, 12 + i)) for i in range(5)]
        shown, rest = tasks.upcoming(items, ['L1'])
        self.assertEqual([t['id'] for t in shown], ['0', '1', '2'])
        self.assertEqual(rest, 2)

    def test_filters(self):
        items = [_task('hidden', list='L9'), _task('done', done=True), _task('ok')]
        shown, rest = tasks.upcoming(items, ['L1'])
        self.assertEqual([t['id'] for t in shown], ['ok'])
        self.assertEqual(rest, 0)

    def test_empty(self):
        self.assertEqual(tasks.upcoming([], ['L1']), ([], 0))
        self.assertEqual(tasks.upcoming([_task('a')], []), ([], 0))
