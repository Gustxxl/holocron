import copy
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


@pytest.fixture
def store(monkeypatch):
    data = {}

    def save(cfg):
        data.clear()
        data.update(copy.deepcopy(cfg))

    monkeypatch.setattr(schedule.config, 'load', lambda: copy.deepcopy(data))
    monkeypatch.setattr(schedule.config, 'save', save)
    return data


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


class TestDates:
    def test_short_hours(self):
        assert dates.parse_period('7-15') == ['07:00', '15:00']

    def test_full_hours(self):
        assert dates.parse_period('07:30 - 15:45') == ['07:30', '15:45']

    def test_two_periods(self):
        assert dates.parse_periods('9-13, 17-21') == [['09:00', '13:00'], ['17:00', '21:00']]

    def test_midnight_end(self):
        assert dates.parse_period('20:00-24:00') == ['20:00', '00:00']

    def test_garbage(self):
        assert dates.parse_period('abc') is None
        assert dates.parse_period('25-26') is None
        assert dates.parse_period('9-9') is None
        assert dates.parse_periods('9-13, x') is None

    def test_dates(self):
        assert dates.parse_date('01-11-2026') == date(2026, 11, 1)
        assert dates.parse_date('01.11.2026') == date(2026, 11, 1)
        assert dates.parse_date('2026-11-01') == date(2026, 11, 1)
        assert dates.parse_date('today', date(2026, 10, 6)) == date(2026, 10, 6)
        assert dates.parse_date('tomorrow', date(2026, 10, 6)) == date(2026, 10, 7)
        assert dates.parse_date('31-02-2026') is None

    def test_monday(self):
        assert dates.monday(date(2026, 10, 11)) == date(2026, 10, 5)
        assert dates.monday(date(2026, 10, 5)) == date(2026, 10, 5)

    def test_merge(self):
        d = lambda n: date(2026, 11, n)
        ranges = [(d(1), d(5)), (d(4), d(10)), (d(12), d(12)), (d(11), d(11)), (d(20), d(21))]
        assert dates.merge_ranges(ranges) == [(d(1), d(12)), (d(20), d(21))]

    def test_night_period(self):
        start, end = dates.period_on(date(2026, 10, 14), '20:00', '07:00')
        assert start == datetime(2026, 10, 14, 20, 0)
        assert end == datetime(2026, 10, 15, 7, 0)


class TestEncode:
    def test_assigns_codes_in_order(self):
        shifts, weeks = schedule.encode_weeks(S.week_days())
        assert weeks == list(S.weeks)
        assert shifts == S.shifts

    def test_reuses_existing_codes(self):
        days = [[['07:00', '15:00']]] * 5 + [[['07:00', '10:00']], None]
        _, weeks = schedule.encode_weeks([days], {'Z': [['07:00', '15:00']]})
        assert weeks == ['ZZZZZA-']

    def test_drops_unused_shifts(self):
        shifts, _ = schedule.encode_weeks([[None] * 7], S.shifts)
        assert shifts == {}


class TestCycle:
    def test_far_dates_match_stepping(self):
        for offset in range(-730, 731, 3):
            d = S.start + timedelta(days=offset)
            assert S.code_on(d) == _stepped_code(d, S)

    def test_week_of(self):
        assert S.week_of(date(2026, 10, 14)) == 1
        assert S.week_of(date(2026, 11, 16)) == 0

    def test_start_for_week(self):
        start = schedule.start_for_week(2, date(2026, 10, 6))
        assert start == date(2026, 9, 28)
        assert replace(S, start=start).week_of(date(2026, 10, 6)) == 1

    def test_start_snaps_to_monday(self):
        assert schedule._clean_start('2026-10-08') == date(2026, 10, 5)


class TestStatus:
    def test_night_crosses_midnight(self):
        sh = S.shifts_on(date(2026, 10, 14))[0]
        assert sh.end == datetime(2026, 10, 15, 7, 0)

    def test_on_night_shift_after_midnight(self):
        st = S.status(datetime(2026, 10, 15, 3, 0))
        assert st.on and st.shift.code == 'C'

    def test_next_shift_after_days_off(self):
        st = S.status(datetime(2026, 10, 11, 11, 0))
        assert not st.on
        assert st.shift.start == datetime(2026, 10, 14, 20, 0)

    def test_split_shift_gap(self):
        s = replace(S, shifts={'S': [['09:00', '13:00'], ['17:00', '21:00']]}, weeks=('SSSSSSS',))
        st = s.status(datetime(2026, 10, 5, 15, 0))
        assert not st.on
        assert st.shift.start == datetime(2026, 10, 5, 17, 0)

    def test_disabled(self):
        assert replace(S, enabled=False).status(datetime(2026, 10, 5, 10, 0)) is None


class TestVacations:
    def test_vacation_day_is_off(self):
        s = replace(S, vacations=((date(2026, 10, 5), date(2026, 10, 11)),))
        assert s.code_on(date(2026, 10, 6)) == schedule.OFF
        assert s.code_on(date(2026, 10, 14)) == 'C'

    def test_status_on_vacation(self):
        s = replace(S, vacations=((date(2026, 10, 5), date(2026, 10, 11)),))
        st = s.status(datetime(2026, 10, 6, 10, 0))
        assert not st.on
        assert st.vacation == (date(2026, 10, 5), date(2026, 10, 11))
        assert st.shift.start == datetime(2026, 10, 14, 20, 0)

    def test_vacation_longer_than_cycle(self):
        s = replace(S, vacations=((date(2026, 10, 5), date(2027, 3, 1)),))
        sh = s.next_shift(datetime(2026, 10, 5, 0, 0))
        assert sh is not None and sh.start.date() >= date(2027, 3, 2)


class TestProblems:
    def test_complete(self):
        assert S.problems() == []

    def test_unknown_code(self):
        assert 'shift X not defined' in replace(S, weeks=('AAAAAX-',)).problems()

    def test_only_days_off(self):
        assert 'weeks have no shifts' in replace(S, weeks=('-------',)).problems()

    def test_short_week(self):
        assert 'week 1 needs 7 days' in replace(S, weeks=('AAA',)).problems()

    def test_no_weeks(self):
        assert 'no weeks' in replace(S, weeks=()).problems()

    def test_no_start(self):
        assert 'current week not set' in replace(S, start=None).problems()


class TestStorage:
    def test_weeks_round_trip(self, store):
        schedule.save_weeks(S.week_days())
        loaded = schedule.load()
        assert loaded.weeks == S.weeks
        assert loaded.shifts == S.shifts

    def test_codes_stable_after_edit(self, store):
        schedule.save_weeks(S.week_days())
        weeks = schedule.load().week_days()
        weeks[0][0] = None
        schedule.save_weeks(weeks)
        assert schedule.load().weeks == ('-AAAABB',) + S.weeks[1:]

    def test_too_many_weeks(self, store):
        with pytest.raises(ValueError):
            schedule.save_weeks([[None] * 7] * (schedule.MAX_WEEKS + 1))

    def test_current_week(self, store):
        schedule.set_current_week(2, date(2026, 10, 6))
        assert schedule.load().start == date(2026, 9, 28)

    def test_vacations_merge(self, store):
        d = lambda n: date(2026, 11, n)
        schedule.save_vacations([(d(1), d(5)), (d(6), d(8))])
        assert schedule.load().vacations == ((d(1), d(8)),)

    def test_enable(self, store):
        schedule.set_enabled(True)
        assert schedule.load().enabled

    def test_reset_keeps_vacations(self, store):
        schedule.save_weeks(S.week_days())
        schedule.set_current_week(1)
        schedule.save_vacations([(date(2026, 11, 1), date(2026, 11, 14))])
        schedule.reset()
        loaded = schedule.load()
        assert loaded.weeks == () and loaded.shifts == {} and loaded.start is None
        assert loaded.vacations

    def test_broken_config(self, store):
        store['schedule'] = {
            'enabled': 'yes',
            'weeks': 'AAAAAAA',
            'shifts': ['A'],
            'start': 'soon',
            'vacations': [1, {'from': 'x'}],
        }
        loaded = schedule.load()
        assert loaded.weeks == () and loaded.shifts == {}
        assert loaded.start is None and loaded.vacations == ()

    def test_empty_config(self, store):
        assert schedule.load() == schedule.Schedule()
