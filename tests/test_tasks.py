import unittest
from datetime import date, datetime

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
        return tasks.parse_add(text, LISTS, default, POINTS, NOW.date())

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

    def _due(self, text):
        draft, problem = self._add(text)
        self.assertIsNone(problem)
        return draft['title'], draft['due']

    def test_time_today(self):
        self.assertEqual(self._due('Check 22:05'), ('Check', datetime(2026, 10, 11, 22, 5)))

    def test_time_and_date_anywhere(self):
        self.assertEqual(self._due('0:05 Check tomorrow backups'), ('Check backups', datetime(2026, 10, 12, 0, 5)))

    def test_date_only_is_all_day(self):
        title, due = self._due('Renew 20-10')
        self.assertEqual((title, due), ('Renew', date(2026, 10, 20)))
        self.assertNotIsInstance(due, datetime)

    def test_no_time(self):
        self.assertEqual(self._due('bread'), ('bread', None))

    def test_bounds(self):
        self.assertEqual(self._due('Check 0:00')[1], datetime(2026, 10, 11, 0, 0))
        self.assertEqual(self._due('Check 23:59')[1], datetime(2026, 10, 11, 23, 59))
        self.assertEqual(self._due('Check 24:00')[1], datetime(2026, 10, 11, 0, 0))

    def test_second_time_and_date_stay_in_text(self):
        self.assertEqual(self._due('Swap 10:00 11:00 today tomorrow'),
                         ('Swap 11:00 tomorrow', datetime(2026, 10, 11, 10, 0)))

    def test_with_list_and_place(self):
        draft, _ = self._add('Lock up 22:05 @home #pets')
        self.assertEqual((draft['title'], draft['list'], draft['place'], draft['due']),
                         ('Lock up', 'L5', POINTS['home'], datetime(2026, 10, 11, 22, 5)))

    def test_cyrillic(self):
        draft, _ = self._add('Проверить Альфа 00:05 #Покупки')
        self.assertEqual((draft['title'], draft['list'], draft['due']),
                         ('Проверить Альфа', 'L3', datetime(2026, 10, 11, 0, 5)))

    def test_bad_time(self):
        for when in ('25:00', '23:60'):
            with self.subTest(when=when):
                self.assertEqual(self._problem(f'Check {when}'), f'No such time: {when}')

    def test_period(self):
        for text in ('Check 22:00-23:00', 'Check 22:00–23:00'):
            with self.subTest(text=text):
                self.assertEqual(self._problem(text), 'Use one time, e.g. 22:05')

    def test_time_alone(self):
        self.assertEqual(self._problem('22:05 tomorrow #work'), 'Type the reminder text')

    def test_odd_digits(self):
        self.assertEqual(self._due('Check ²2:05'), ('Check ²2:05', None))
        self.assertEqual(self._due('Check ٢٢:٠٥')[1], datetime(2026, 10, 11, 22, 5))


class EditText(unittest.TestCase):
    TASK = {'id': 'a', 'title': 'Call bank', 'notes': 'ask about card', 'list': 'L1', 'list_name': 'Work',
            'due': None, 'all_day': False}

    def _task(self, **extra):
        return {**self.TASK, **extra}

    def _changes(self, text, task=None):
        return tasks.changes(task or self.TASK, text, LISTS, NOW.date(), NOW)

    def test_to_text(self):
        self.assertEqual(tasks.to_text(self.TASK, NOW.date()), 'Call bank #Work\n\nask about card')
        self.assertEqual(tasks.to_text({'title': 'x', 'notes': ''}, NOW.date()), 'x')

    def test_to_text_due(self):
        cases = [(datetime(2026, 10, 12, 9, 30), False, 'Call bank 12-10 09:30 #Work'),
                 (datetime(2026, 10, 20), True, 'Call bank 20-10 #Work'),
                 (datetime(2027, 1, 5, 9, 0), False, 'Call bank 05-01-2027 09:00 #Work')]
        for due, all_day, line in cases:
            with self.subTest(line=line):
                self.assertEqual(tasks.first_line(self._task(due=due, all_day=all_day), NOW.date()), line)

    def test_no_changes(self):
        self.assertEqual(self._changes(' Call bank #Work \n\n ask about card \n'), ({}, None))

    def test_untouched_line_keeps_time_in_title(self):
        task = self._task(title='Call at 10:30', due=datetime(2026, 10, 11, 15, 0))
        self.assertEqual(self._changes(tasks.to_text(task, NOW.date()), task), ({}, None))

    def test_title_only(self):
        self.assertEqual(self._changes('Call the bank #Work\n\nask about card'), ({'title': 'Call the bank'}, None))

    def test_notes_changed_and_cleared(self):
        self.assertEqual(self._changes('Call bank #Work\nnew'), ({'notes': 'new'}, None))
        self.assertEqual(self._changes('Call bank #Work'), ({'notes': ''}, None))

    def test_empty_cancels(self):
        self.assertEqual(self._changes('  \n\n'), (None, 'Empty text — edit cancelled'))
        self.assertEqual(self._changes('\n\nonly notes')[0], {'title': 'only notes', 'notes': ''})

    def test_move_to_list(self):
        self.assertEqual(self._changes('Call bank #Pets\n\nask about card'), ({'list': 'L5'}, None))

    def test_no_tag_keeps_list(self):
        self.assertEqual(self._changes('Call bank\n\nask about card'), ({}, None))

    def test_set_time(self):
        due = datetime(2026, 10, 11, 18, 0)
        self.assertEqual(self._changes('Call bank 18:00\n\nask about card'), ({'due': due, 'alarm': due}, None))

    def test_alarm_keeps_offset(self):
        task = self._task(due=datetime(2026, 10, 11, 12, 0), alarm=datetime(2026, 10, 11, 11, 50))
        found, _ = self._changes('Call bank 11-10 15:00\n\nask about card', task)
        self.assertEqual(found, {'due': datetime(2026, 10, 11, 15, 0), 'alarm': datetime(2026, 10, 11, 14, 50)})

    def test_no_alarm_stays_without(self):
        task = self._task(due=datetime(2026, 10, 11, 12, 0), alarm=None)
        found, _ = self._changes('Call bank 11-10 15:00\n\nask about card', task)
        self.assertEqual(found, {'due': datetime(2026, 10, 11, 15, 0)})

    def test_clear_due(self):
        task = self._task(due=datetime(2026, 10, 11, 12, 0), alarm=datetime(2026, 10, 11, 12, 0))
        self.assertEqual(self._changes('Call bank\n\nask about card', task), ({'due': None, 'alarm': None}, None))

    def test_to_all_day(self):
        task = self._task(due=datetime(2026, 10, 11, 12, 0), alarm=datetime(2026, 10, 11, 12, 0))
        found, _ = self._changes('Call bank 20-10\n\nask about card', task)
        self.assertEqual(found, {'due': date(2026, 10, 20), 'alarm': None})

    def test_all_day_same_day_unchanged(self):
        task = self._task(due=datetime(2026, 10, 20), all_day=True)
        self.assertEqual(self._changes('Call bank 20-10 #Pets\n\nask about card', task), ({'list': 'L5'}, None))

    def test_relative(self):
        found, _ = self._changes('Call bank +30\n\nask about card')
        self.assertEqual(found['due'], datetime(2026, 10, 11, 15, 30))

    def test_problems(self):
        self.assertEqual(self._changes('Call bank 25:00'), (None, 'No such time: 25:00'))
        self.assertEqual(self._changes('Call bank @home'), (None, 'No waypoint @home'))
        self.assertEqual(self._changes('Call bank #zzz'), (None, 'No list #zzz'))


class Apply(unittest.TestCase):
    def test_due_and_list(self):
        task = {'title': 'Alpha', 'due': datetime(2026, 10, 11, 12, 0), 'all_day': False, 'list': 'L1', 'list_name': 'Work'}
        tasks.apply(task, {'due': date(2026, 10, 20), 'list': 'L5', 'alarm': None}, LISTS)
        self.assertEqual((task['due'], task['all_day'], task['list'], task['list_name'], task['alarm']),
                         (datetime(2026, 10, 20), True, 'L5', 'Pets', None))
        tasks.apply(task, {'due': datetime(2026, 10, 21, 9, 0)}, LISTS)
        self.assertEqual((task['due'], task['all_day']), (datetime(2026, 10, 21, 9, 0), False))


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
