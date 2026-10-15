import base64
import json
import unittest
from datetime import date, datetime, timezone
from unittest import mock

from core import schedule, zones

HAS_DB = zones.get('Europe/Moscow') is not None
WINTER = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
SUMMER = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


class Format(unittest.TestCase):
    def test_utc(self):
        from datetime import timedelta
        self.assertEqual(zones.utc(timedelta(hours=3)), 'UTC+3')
        self.assertEqual(zones.utc(timedelta(hours=5, minutes=30)), 'UTC+5:30')
        self.assertEqual(zones.utc(timedelta(hours=-5)), 'UTC-5')
        self.assertEqual(zones.utc(timedelta(0)), 'UTC+0')

    def test_valid(self):
        self.assertTrue(zones.valid('Europe/Moscow'))
        self.assertTrue(zones.valid('America/Argentina/Buenos_Aires'))
        self.assertFalse(zones.valid('../etc/passwd'))
        self.assertFalse(zones.valid(''))
        self.assertFalse(zones.valid(None))

    def test_bad_name_not_loaded(self):
        self.assertIsNone(zones.get('../../etc/passwd'))
        self.assertIsNone(zones.get('Nowhere/City'))

    def test_label(self):
        self.assertEqual(zones.label('America/New_York'), 'New York')


@unittest.skipUnless(HAS_DB, 'no time zone database')
class Find(unittest.TestCase):
    def test_city(self):
        self.assertEqual(zones.find('moscow'), ['Europe/Moscow'])

    def test_full_name(self):
        self.assertEqual(zones.find('Europe/Moscow'), ['Europe/Moscow'])

    def test_space_for_underscore(self):
        self.assertIn('America/New_York', zones.find('new york'))

    def test_part(self):
        self.assertIn('Asia/Yekaterinburg', zones.find('yekat'))

    def test_offset(self):
        found = zones.find('+5', WINTER)
        self.assertIn('Asia/Yekaterinburg', found)
        self.assertNotIn('Europe/Moscow', found)

    def test_half_hour(self):
        self.assertIn('Asia/Kolkata', zones.find('UTC+5:30', WINTER))

    def test_offset_follows_season(self):
        self.assertIn('Europe/Belgrade', zones.find('+2', SUMMER))
        self.assertNotIn('Europe/Belgrade', zones.find('+2', WINTER))

    def test_nothing(self):
        self.assertEqual(zones.find('qwertyzone'), [])

    def test_no_aliases(self):
        self.assertFalse([n for n in zones.names() if n.startswith(('Etc/', 'US/'))])


@unittest.skipUnless(HAS_DB, 'no time zone database')
class Local(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(zones, '_local', return_value=zones.get('Europe/Belgrade'))
        patch.start()
        self.addCleanup(patch.stop)

    def _sched(self, **extra):
        return schedule.Schedule(enabled=True, shifts={'A': [['01:00', '09:00']]}, weeks=('AAAAAAA',),
                                 start=schedule.EPOCH, zone='Asia/Yekaterinburg', **extra)

    def test_winter(self):
        self.assertEqual(zones.to_local(datetime(2026, 1, 15, 9, 0), 'Europe/Moscow'), datetime(2026, 1, 15, 7, 0))

    def test_summer(self):
        self.assertEqual(zones.to_local(datetime(2026, 7, 15, 9, 0), 'Europe/Moscow'), datetime(2026, 7, 15, 8, 0))

    def test_no_zone(self):
        dt = datetime(2026, 1, 15, 9, 0)
        self.assertEqual(zones.to_local(dt, None), dt)
        self.assertEqual(zones.to_local(dt, 'Nowhere/City'), dt)

    def test_shift_moves_to_previous_day(self):
        found = self._sched().shifts_on(date(2026, 1, 15))
        self.assertEqual([(s.start, s.end) for s in found],
                         [(datetime(2026, 1, 15, 21, 0), datetime(2026, 1, 16, 5, 0))])

    def test_status_in_local_time(self):
        self.assertTrue(self._sched().status(datetime(2026, 1, 15, 22, 0)).on)

    def test_vacation_by_local_day(self):
        sched = self._sched(vacations=((date(2026, 1, 15), date(2026, 1, 15)),))
        self.assertEqual(sched.shifts_on(date(2026, 1, 15)), [])

    def test_differs(self):
        self.assertTrue(zones.differs('Europe/Moscow', WINTER))
        self.assertFalse(zones.differs('Europe/Belgrade', WINTER))


class Share(unittest.TestCase):
    SHIFTS = {'A': [['09:00', '21:00']]}

    def test_zone_travels(self):
        sched = schedule.Schedule(shifts=self.SHIFTS, weeks=('AAAAA--',), zone='Europe/Moscow')
        self.assertEqual(schedule.read_code(schedule.share_code(sched)).zone, 'Europe/Moscow')

    def test_old_code_is_local(self):
        sched = schedule.Schedule(shifts=self.SHIFTS, weeks=('AAAAA--',))
        self.assertIsNone(schedule.read_code(schedule.share_code(sched)).zone)

    def test_bad_zone_dropped(self):
        raw = json.dumps({'s': self.SHIFTS, 'w': ['AAAAA--'], 'z': '../x'}).encode('utf-8')
        code = schedule.SHARE_PREFIX + base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
        self.assertIsNone(schedule.read_code(code).zone)


if __name__ == '__main__':
    unittest.main()
