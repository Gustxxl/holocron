import unittest
from datetime import datetime

from core import tasks

NOW = datetime(2026, 10, 11, 15, 0)

LISTS = [
    {'id': 'L1', 'title': 'Work'},
    {'id': 'L2', 'title': 'Покупки для дома🏡'},
    {'id': 'L3', 'title': 'Покупки'},
    {'id': 'L4', 'title': 'Personal'},
    {'id': 'L5', 'title': 'Pets'},
]


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


class Numbered(unittest.TestCase):
    def test_flat_in_display_order(self):
        a, b, c = _task('a'), _task('b'), _task('c', list='L2')
        self.assertEqual(tasks.numbered([('A', [a, b]), ('B', [c])]), [a, b, c])


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


POINTS = {'home': {'address': 'Main 1', 'radius': 100, 'proximity': 'arriving'}}


class ParseAdd(unittest.TestCase):
    def _add(self, text, default='L1'):
        return tasks.parse_add(text, LISTS, default, POINTS)

    def _ok(self, text, default='L1'):
        draft, problem = self._add(text, default)
        self.assertIsNone(problem)
        return draft['title'], draft['list']

    def _problem(self, text, default='L1'):
        return self._add(text, default)[1]

    def test_default_list(self):
        self.assertEqual(self._ok(' Buy  bread '), ('Buy bread', 'L1'))

    def test_no_default(self):
        self.assertEqual(self._problem('Buy bread', None), 'Choose lists in settings')

    def test_exact_wins_over_prefix(self):
        self.assertEqual(self._ok('хлеб #Покупки'), ('хлеб', 'L3'))

    def test_prefix_ignores_emoji_and_spaces(self):
        self.assertEqual(self._ok('хлеб #покупки_для'), ('хлеб', 'L2'))

    def test_tag_in_the_middle(self):
        self.assertEqual(self._ok('call #work bob'), ('call bob', 'L1'))

    def test_hash_and_at_inside_word_are_text(self):
        self.assertEqual(self._ok('C# docs to a@b.com'), ('C# docs to a@b.com', 'L1'))

    def test_several_matches(self):
        self.assertEqual(self._problem('walk #pe'), '#pe matches several lists')

    def test_unknown_list(self):
        self.assertEqual(self._problem('walk #zzz'), 'No list #zzz')

    def test_empty_text(self):
        self.assertEqual(self._problem('  #work @home'), 'Type the reminder text')

    def test_two_tags(self):
        self.assertEqual(self._problem('walk #work #pets'), 'Use one #list')

    def test_place(self):
        draft, _ = self._add('bread @Home #work')
        self.assertEqual((draft['title'], draft['list'], draft['place']), ('bread', 'L1', POINTS['home']))

    def test_no_place(self):
        self.assertIsNone(self._add('bread')[0]['place'])

    def test_unknown_place(self):
        self.assertEqual(self._problem('bread @gym'), 'No waypoint @gym')

    def test_two_places(self):
        self.assertEqual(self._problem('bread @home @home'), 'Use one @waypoint')


class EditText(unittest.TestCase):
    TASK = {'id': 'a', 'title': 'Call bank', 'notes': 'ask about card'}

    def test_to_text(self):
        self.assertEqual(tasks.to_text(self.TASK), 'Call bank\n\nask about card')
        self.assertEqual(tasks.to_text({'title': 'x', 'notes': ''}), 'x')

    def test_no_changes(self):
        self.assertEqual(tasks.changes(self.TASK, ' Call bank \n\n ask about card \n'), {})

    def test_title_only(self):
        self.assertEqual(tasks.changes(self.TASK, 'Call the bank\n\nask about card'), {'title': 'Call the bank'})

    def test_notes_changed_and_cleared(self):
        self.assertEqual(tasks.changes(self.TASK, 'Call bank\nnew'), {'notes': 'new'})
        self.assertEqual(tasks.changes(self.TASK, 'Call bank'), {'notes': ''})

    def test_empty_cancels(self):
        self.assertIsNone(tasks.changes(self.TASK, '  \n\n'))
        self.assertEqual(tasks.changes(self.TASK, '\n\nonly notes'), {'title': 'only notes', 'notes': ''})


class ListWithSpaces(unittest.TestCase):
    LISTS = [{'id': 'L1', 'title': 'Home'}, {'id': 'L2', 'title': 'Home Office'}, {'id': 'L3', 'title': 'Work'}]

    def _add(self, text):
        return tasks.parse_add(text, self.LISTS, 'L3')

    def _ok(self, text):
        draft, problem = self._add(text)
        self.assertIsNone(problem)
        return draft['title'], draft['list']

    def test_full_title(self):
        self.assertEqual(self._ok('Buy chair #Home Office'), ('Buy chair', 'L2'))

    def test_any_case(self):
        self.assertEqual(self._ok('Buy chair #home office'), ('Buy chair', 'L2'))

    def test_text_after_tag(self):
        self.assertEqual(self._ok('#Home Office buy chair'), ('buy chair', 'L2'))

    def test_longer_title_wins(self):
        self.assertEqual(self._ok('Lamp #Home'), ('Lamp', 'L1'))
        self.assertEqual(self._ok('Lamp #Home Office'), ('Lamp', 'L2'))

    def test_word_boundary(self):
        self.assertEqual(self._ok('Buy #Home officially'), ('Buy officially', 'L1'))

    def test_two_lists(self):
        self.assertEqual(self._add('Desk #Home Office #Work')[1], 'Use one #list')
