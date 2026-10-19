import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from core import dates, events
from core.sources import ekctl

CALENDARS = {'calendars': [
    {'id': 'C1', 'title': 'Work', 'type': 'event'},
    {'id': 'R1', 'title': 'Groceries', 'type': 'reminder'},
    {'title': 'no id', 'type': 'event'},
], 'status': 'success'}

EVENTS = {'events': [
    {'id': 'E1', 'title': 'Standup', 'calendar': {'id': 'C1', 'title': 'Work'},
     'startDate': '2026-10-16T10:00:00', 'endDate': '2026-10-16T10:15:00',
     'location': None, 'notes': 'Join https://meet.google.com/abc-defg-hij.', 'allDay': False},
    {'id': 'E2', 'title': ' ', 'calendar': {'id': 'C1', 'title': 'Work'},
     'startDate': '2026-10-17', 'endDate': '2026-10-18', 'location': 'Room 1', 'notes': None,
     'allDay': True, 'url': 'https://example.com/x'},
    {'id': 'E3', 'title': 'No start'},
    'junk',
], 'status': 'success'}

LISTS = [{'id': 'C1', 'title': 'Work'}, {'id': 'C2', 'title': 'Home'}]
TODAY = date(2026, 10, 16)
NOW = datetime(2026, 10, 16, 12)


def _event(start, end, list_id='C1', all_day=False, title='x'):
    return {'id': title, 'title': title, 'start': start, 'end': end, 'all_day': all_day,
            'list': list_id, 'list_name': '', 'place': '', 'notes': '', 'url': ''}


def _utc(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Parse(unittest.TestCase):
    def test_lists_skip_reminder_lists(self):
        self.assertEqual(ekctl.parse_lists(CALENDARS), [{'id': 'C1', 'title': 'Work'}])

    def test_items(self):
        found = {e['id']: e for e in ekctl.parse_items(EVENTS)}
        self.assertEqual(sorted(found), ['E1', 'E2'])
        self.assertEqual(found['E1']['start'], datetime(2026, 10, 16, 10))
        self.assertEqual(found['E1']['end'], datetime(2026, 10, 16, 10, 15))
        self.assertEqual((found['E1']['list'], found['E1']['list_name']), ('C1', 'Work'))
        self.assertEqual(found['E2']['title'], '(untitled)')
        self.assertTrue(found['E2']['all_day'])
        self.assertEqual(found['E2']['place'], 'Room 1')
        self.assertEqual(found['E2']['url'], 'https://example.com/x')
        self.assertEqual(found['E1']['invitees'], '')

    def test_not_events(self):
        self.assertIsNone(ekctl.parse_lists([]))
        self.assertIsNone(ekctl.parse_items({'status': 'error'}))


class Add(unittest.TestCase):
    def test_command(self):
        start, end = datetime(2026, 10, 16, 12, 30), datetime(2026, 10, 16, 13, 30)
        with patch.object(ekctl.cli, 'run_ok', return_value=True) as run:
            ekctl.add('Lunch', 'C1', start, end)
        run.assert_called_once_with('ekctl', 'add', 'event', '--calendar', 'C1', '--title', 'Lunch',
                                    '--start', _utc(start), '--end', _utc(end))


class Items(unittest.TestCase):
    def test_one_call_for_known_calendars(self):
        with patch.object(ekctl.sources, 'selected', return_value=['C1', 'GONE', 'C2']), \
             patch.object(ekctl, 'lists', return_value=LISTS), \
             patch.object(ekctl.cli, 'run_json', return_value=EVENTS) as run:
            found = ekctl.items()
        self.assertEqual([e['id'] for e in found], ['E1', 'E2'])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[3:5], ('--calendar', 'C1,C2'))

    def test_nothing_selected(self):
        with patch.object(ekctl.sources, 'selected', return_value=['GONE']), \
             patch.object(ekctl, 'lists', return_value=LISTS), \
             patch.object(ekctl.cli, 'run_json') as run:
            self.assertEqual(ekctl.items(), [])
        run.assert_not_called()

    def test_failed_read(self):
        with patch.object(ekctl.sources, 'selected', return_value=['C1']), \
             patch.object(ekctl, 'lists', return_value=LISTS), \
             patch.object(ekctl.cli, 'run_json', return_value=None):
            self.assertIsNone(ekctl.items())


class Access(unittest.TestCase):
    def test_only_code_two_is_denied(self):
        for code, expected in ((0, True), (1, True), (64, True), (2, False), (None, False)):
            with self.subTest(code=code), patch.object(ekctl.cli, 'run_code', return_value=code):
                self.assertEqual(ekctl.authorized(), expected)


class ParseAdd(unittest.TestCase):
    def _add(self, text):
        return events.parse_add(text, LISTS, 'C1', TODAY)

    def test_time_gets_an_hour(self):
        draft, problem = self._add('Standup 10:00')
        self.assertIsNone(problem)
        self.assertEqual(draft, {'title': 'Standup', 'list': 'C1',
                                 'start': datetime(2026, 10, 16, 10), 'end': datetime(2026, 10, 16, 11)})

    def test_date_period_and_calendar(self):
        draft, _ = self._add('Dentist tomorrow 15:30-16:15 #home')
        self.assertEqual((draft['title'], draft['list']), ('Dentist', 'C2'))
        self.assertEqual(draft['start'], datetime(2026, 10, 17, 15, 30))
        self.assertEqual(draft['end'], datetime(2026, 10, 17, 16, 15))

    def test_short_date(self):
        draft, _ = self._add('Review 20-10 9:00')
        self.assertEqual(draft['start'], datetime(2026, 10, 20, 9))

    def test_problems(self):
        for text in ('10:00', 'Standup', 'Standup 25:00', 'Standup 10:00 #a #b', 'Standup 10:00 #gym'):
            with self.subTest(text=text):
                draft, problem = self._add(text)
                self.assertIsNone(draft)
                self.assertTrue(problem)

    def test_calendar_with_spaces(self):
        lists = [*LISTS, {'id': 'C3', 'title': 'Team Sync'}]
        draft, _ = events.parse_add('Retro 15:00 #Team Sync', lists, 'C1', TODAY)
        self.assertEqual((draft['title'], draft['list']), ('Retro', 'C3'))

    def test_calendar_words(self):
        self.assertEqual(self._add('Standup 10:00 #gym')[1], 'No calendar #gym')
        self.assertEqual(events.parse_add('Standup 10:00', LISTS, None, TODAY)[1], 'Choose calendars in settings')


class Upcoming(unittest.TestCase):
    def test_skips_finished_and_hidden(self):
        items = [
            _event(datetime(2026, 10, 16, 9), datetime(2026, 10, 16, 10), title='done'),
            _event(datetime(2026, 10, 16, 11), datetime(2026, 10, 16, 13), title='now'),
            _event(datetime(2026, 10, 17, 9), datetime(2026, 10, 17, 10), title='later'),
            _event(datetime(2026, 10, 16, 14), datetime(2026, 10, 16, 15), list_id='C2', title='hidden'),
            _event(datetime(2026, 10, 16), datetime(2026, 10, 17), all_day=True, title='day'),
            _event(datetime(2026, 10, 15), datetime(2026, 10, 16), all_day=True, title='yesterday'),
        ]
        found = events.upcoming(items, ['C1'], NOW)
        self.assertEqual([e['title'] for e in found], ['day', 'now', 'later'])

    def test_started_earlier_shows_today(self):
        items = [_event(datetime(2026, 10, 15, 9), datetime(2026, 10, 17), title='trip'),
                 _event(datetime(2026, 10, 17, 9), datetime(2026, 10, 17, 10), title='later')]
        days = [(d, [e['title'] for e in group]) for d, group in events.by_day(items, NOW)]
        self.assertEqual(days, [(date(2026, 10, 16), ['trip']), (date(2026, 10, 17), ['later'])])


class Link(unittest.TestCase):
    def test_meeting_link_wins(self):
        event = {'url': 'https://example.com/agenda', 'place': '',
                 'notes': 'Join: https://us02web.zoom.us/j/123?pwd=x.'}
        self.assertEqual(events.link(event), 'https://us02web.zoom.us/j/123?pwd=x')

    def test_any_link(self):
        self.assertEqual(events.link({'url': 'https://example.com/x', 'place': '', 'notes': ''}),
                         'https://example.com/x')

    def test_none(self):
        self.assertEqual(events.link({'url': '', 'place': 'Room 1', 'notes': None}), '')

    def test_calendar_page_is_not_a_meeting(self):
        event = {'url': 'https://calendar.yandex.ru/event?event_id=1234', 'place': '', 'notes': ''}
        self.assertEqual(events.meeting(event), '')
        self.assertEqual(events.link(event), 'https://calendar.yandex.ru/event?event_id=1234')

    def test_telemost(self):
        event = {'url': '', 'place': '', 'notes': 'Ссылка на видеовстречу: https://telemost.360.yandex.ru/j/1234'}
        self.assertEqual(events.meeting(event), 'https://telemost.360.yandex.ru/j/1234')

    def test_invitees(self):
        event = {'url': '', 'place': '', 'notes': '',
                 'invitees': "{'name': 'Room', 'url': 'https://zoom.us/j/9'}"}
        self.assertEqual(events.meeting(event), 'https://zoom.us/j/9')


class Within(unittest.TestCase):
    def test_days(self):
        self.assertTrue(dates.within(datetime(2026, 10, 17, 23), NOW, 2))
        self.assertFalse(dates.within(datetime(2026, 10, 18), NOW, 2))
        self.assertTrue(dates.within(datetime(2026, 10, 1), NOW, 1))
        self.assertTrue(dates.within(None, NOW, 0))
        self.assertFalse(dates.within(None, NOW, 1))
