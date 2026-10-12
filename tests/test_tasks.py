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


class ParseAdd(unittest.TestCase):
    def _add(self, text, default='L1'):
        return tasks.parse_add(text, LISTS, default)

    def test_default_list(self):
        self.assertEqual(self._add(' Buy  bread '), ('Buy bread', 'L1', None))

    def test_no_default(self):
        self.assertEqual(self._add('Buy bread', None)[2], 'Choose lists in settings')

    def test_exact_wins_over_prefix(self):
        self.assertEqual(self._add('хлеб #Покупки')[:2], ('хлеб', 'L3'))

    def test_prefix_ignores_emoji_and_spaces(self):
        self.assertEqual(self._add('хлеб #покупки_для')[:2], ('хлеб', 'L2'))

    def test_tag_in_the_middle(self):
        self.assertEqual(self._add('call #work bob')[:2], ('call bob', 'L1'))

    def test_hash_inside_word_is_text(self):
        self.assertEqual(self._add('C# docs'), ('C# docs', 'L1', None))

    def test_several_matches(self):
        self.assertEqual(self._add('walk #pe')[2], '#pe matches several lists')

    def test_unknown_list(self):
        self.assertEqual(self._add('walk #zzz')[2], 'No list #zzz')

    def test_empty_text(self):
        self.assertEqual(self._add('  #work')[2], 'Type the reminder text')

    def test_two_tags(self):
        self.assertEqual(self._add('walk #work #pets')[2], 'Use one #list')


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
