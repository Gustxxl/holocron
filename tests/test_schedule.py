import copy
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from unittest.mock import patch

from core import dates, schedule

S = schedule.Schedule(
    enabled=True,
    shifts={
        'A': [['07:00', '15:00']],
        'B': [['07:00', '10:00']],
        'C': [['20:00', '07:00']],
        'D': [['12:00', '20:00']],
        'E': [['10:00', '20:00']],
        'F': [['10:00', '18:00']],
        'G': [['08:00', '20:00']],
    },
    weeks=('AAAAABB', '--CCC--', 'DDDDDE-', 'CC---CC', '--FFF-G', 'FF-----'),
    start=date(2026, 10, 5),
)


def _stepped_code(d, s):
    cur, week, day = s.start, 0, 0
    step = 1 if d >= cur else -1
    while cur != d:
        cur += timedelta(days=step)
        day += step
        if day == 7:
            day, week = 0, (week + 1) % len(s.weeks)
        elif day == -1:
            day, week = 6, (week - 1) % len(s.weeks)
    return s.weeks[week][day]


class TestDates(unittest.TestCase):
    def test_short_hours(self):
        self.assertEqual(dates.parse_period('7-15'), ['07:00', '15:00'])

    def test_full_hours(self):
        self.assertEqual(dates.parse_period('07:30 - 15:45'), ['07:30', '15:45'])

    def test_two_periods(self):
        self.assertEqual(dates.parse_periods('9-13, 17-21'), [['09:00', '13:00'], ['17:00', '21:00']])

    def test_midnight_end(self):
        self.assertEqual(dates.parse_period('20:00-24:00'), ['20:00', '00:00'])

    def test_garbage(self):
        self.assertIsNone(dates.parse_period('abc'))
        self.assertIsNone(dates.parse_period('25-26'))
        self.assertIsNone(dates.parse_period('9-9'))
        self.assertIsNone(dates.parse_periods('9-13, x'))

    def test_dates(self):
        self.assertEqual(dates.parse_date('01-11-2026'), date(2026, 11, 1))
        self.assertEqual(dates.parse_date('01.11.2026'), date(2026, 11, 1))
        self.assertEqual(dates.parse_date('2026-11-01'), date(2026, 11, 1))
        self.assertEqual(dates.parse_date('today', date(2026, 10, 6)), date(2026, 10, 6))
        self.assertEqual(dates.parse_date('tomorrow', date(2026, 10, 6)), date(2026, 10, 7))
        self.assertIsNone(dates.parse_date('31-02-2026'))

    def test_monday(self):
        self.assertEqual(dates.monday(date(2026, 10, 11)), date(2026, 10, 5))
        self.assertEqual(dates.monday(date(2026, 10, 5)), date(2026, 10, 5))

    def test_merge(self):
        d = lambda n: date(2026, 11, n)
        ranges = [(d(1), d(5)), (d(4), d(10)), (d(12), d(12)), (d(11), d(11)), (d(20), d(21))]
        self.assertEqual(dates.merge_ranges(ranges), [(d(1), d(12)), (d(20), d(21))])

    def test_night_period(self):
        start, end = dates.period_on(date(2026, 10, 14), '20:00', '07:00')
        self.assertEqual(start, datetime(2026, 10, 14, 20, 0))
        self.assertEqual(end, datetime(2026, 10, 15, 7, 0))


class TestEncode(unittest.TestCase):
    def test_assigns_codes_in_order(self):
        shifts, weeks = schedule.encode_weeks(S.week_days())
        self.assertEqual(weeks, list(S.weeks))
        self.assertEqual(shifts, S.shifts)

    def test_reuses_existing_codes(self):
        days = [[['07:00', '15:00']]] * 5 + [[['07:00', '10:00']], None]
        _, weeks = schedule.encode_weeks([days], {'Z': [['07:00', '15:00']]})
        self.assertEqual(weeks, ['ZZZZZA-'])

    def test_drops_unused_shifts(self):
        shifts, _ = schedule.encode_weeks([[None] * 7], S.shifts)
        self.assertEqual(shifts, {})


class TestCycle(unittest.TestCase):
    def test_far_dates_match_stepping(self):
        for offset in range(-730, 731, 3):
            d = S.start + timedelta(days=offset)
            self.assertEqual(S.code_on(d), _stepped_code(d, S))

    def test_week_of(self):
        self.assertEqual(S.week_of(date(2026, 10, 14)), 1)
        self.assertEqual(S.week_of(date(2026, 11, 16)), 0)

    def test_start_for_week(self):
        start = schedule.start_for_week(2, date(2026, 10, 6))
        self.assertEqual(start, date(2026, 9, 28))
        self.assertEqual(replace(S, start=start).week_of(date(2026, 10, 6)), 1)

    def test_start_snaps_to_monday(self):
        self.assertEqual(schedule._clean_start('2026-10-08'), date(2026, 10, 5))


class TestStatus(unittest.TestCase):
    def test_night_crosses_midnight(self):
        sh = S.shifts_on(date(2026, 10, 14))[0]
        self.assertEqual(sh.end, datetime(2026, 10, 15, 7, 0))

    def test_on_night_shift_after_midnight(self):
        st = S.status(datetime(2026, 10, 15, 3, 0))
        self.assertTrue(st.on)
        self.assertEqual(st.shift.code, 'C')

    def test_next_shift_after_days_off(self):
        st = S.status(datetime(2026, 10, 11, 11, 0))
        self.assertFalse(st.on)
        self.assertEqual(st.shift.start, datetime(2026, 10, 14, 20, 0))

    def test_split_shift_gap(self):
        s = replace(S, shifts={'S': [['09:00', '13:00'], ['17:00', '21:00']]}, weeks=('SSSSSSS',))
        st = s.status(datetime(2026, 10, 5, 15, 0))
        self.assertFalse(st.on)
        self.assertEqual(st.shift.start, datetime(2026, 10, 5, 17, 0))

    def test_disabled(self):
        self.assertIsNone(replace(S, enabled=False).status(datetime(2026, 10, 5, 10, 0)))


class TestVacations(unittest.TestCase):
    def test_vacation_day_is_off(self):
        s = replace(S, vacations=((date(2026, 10, 5), date(2026, 10, 11)),))
        self.assertEqual(s.code_on(date(2026, 10, 6)), schedule.OFF)
        self.assertEqual(s.code_on(date(2026, 10, 14)), 'C')

    def test_status_on_vacation(self):
        s = replace(S, vacations=((date(2026, 10, 5), date(2026, 10, 11)),))
        st = s.status(datetime(2026, 10, 6, 10, 0))
        self.assertFalse(st.on)
        self.assertEqual(st.vacation, (date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(st.shift.start, datetime(2026, 10, 14, 20, 0))

    def test_vacation_longer_than_cycle(self):
        s = replace(S, vacations=((date(2026, 10, 5), date(2027, 3, 1)),))
        sh = s.next_shift(datetime(2026, 10, 5, 0, 0))
        self.assertIsNotNone(sh)
        self.assertGreaterEqual(sh.start.date(), date(2027, 3, 2))


class TestProblems(unittest.TestCase):
    def test_complete(self):
        self.assertEqual(S.problems(), [])

    def test_unknown_code(self):
        self.assertIn('shift X not defined', replace(S, weeks=('AAAAAX-',)).problems())

    def test_only_days_off(self):
        self.assertIn('weeks have no shifts', replace(S, weeks=('-------',)).problems())

    def test_short_week(self):
        self.assertIn('week 1 needs 7 days', replace(S, weeks=('AAA',)).problems())

    def test_no_weeks(self):
        self.assertIn('no weeks', replace(S, weeks=()).problems())

    def test_no_start(self):
        self.assertIn('current week not set', replace(S, start=None).problems())


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.store = {}

        def save(cfg):
            self.store.clear()
            self.store.update(copy.deepcopy(cfg))

        for name, fn in (('load', lambda: copy.deepcopy(self.store)), ('save', save)):
            patcher = patch.object(schedule.config, name, fn)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_weeks_round_trip(self):
        schedule.save_weeks(S.week_days())
        loaded = schedule.load()
        self.assertEqual(loaded.weeks, S.weeks)
        self.assertEqual(loaded.shifts, S.shifts)

    def test_codes_stable_after_edit(self):
        schedule.save_weeks(S.week_days())
        weeks = schedule.load().week_days()
        weeks[0][0] = None
        schedule.save_weeks(weeks)
        self.assertEqual(schedule.load().weeks, ('-AAAABB',) + S.weeks[1:])

    def test_too_many_weeks(self):
        with self.assertRaises(ValueError):
            schedule.save_weeks([[None] * 7] * (schedule.MAX_WEEKS + 1))

    def test_current_week(self):
        schedule.set_current_week(2, date(2026, 10, 6))
        self.assertEqual(schedule.load().start, date(2026, 9, 28))

    def test_vacations_merge(self):
        d = lambda n: date(2026, 11, n)
        schedule.save_vacations([(d(1), d(5)), (d(6), d(8))])
        self.assertEqual(schedule.load().vacations, ((d(1), d(8)),))

    def test_enable(self):
        schedule.set_enabled(True)
        self.assertTrue(schedule.load().enabled)

    def test_reset_keeps_vacations(self):
        schedule.save_weeks(S.week_days())
        schedule.set_current_week(1)
        schedule.save_vacations([(date(2026, 11, 1), date(2026, 11, 14))])
        schedule.reset()
        loaded = schedule.load()
        self.assertEqual((loaded.weeks, loaded.shifts, loaded.start), ((), {}, None))
        self.assertTrue(loaded.vacations)

    def test_broken_config(self):
        self.store['schedule'] = {
            'enabled': 'yes',
            'weeks': 'AAAAAAA',
            'shifts': ['A'],
            'start': 'soon',
            'vacations': [1, {'from': 'x'}],
        }
        loaded = schedule.load()
        self.assertEqual((loaded.weeks, loaded.shifts), ((), {}))
        self.assertEqual((loaded.start, loaded.vacations), (None, ()))

    def test_empty_config(self):
        self.assertEqual(schedule.load(), schedule.Schedule())


if __name__ == '__main__':
    unittest.main()
