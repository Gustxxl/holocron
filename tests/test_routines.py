import copy
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from datetime import date, datetime
from unittest.mock import Mock, call, patch
from zoneinfo import ZoneInfo

from core import routines, schedule
from screens import main_screen

LISTS = [{'id': 'L1', 'title': 'Todo'}, {'id': 'L2', 'title': 'Список'}]
SCHED = schedule.Schedule(enabled=True, shifts={'N': [['20:00', '08:00']], 'D': [['08:00', '20:00']]},
                          weeks=('NN--DD-',), start=date(2026, 11, 23))
MON = datetime(2026, 11, 23, 12, 0)
WED = datetime(2026, 11, 25, 12, 0)


def _routine(**fields):
    return {'title': 'Check', 'time': '00:05', 'zone': '', 'rule': 'shift', 'list': 'L1', 'last': None, **fields}


class _Config(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        lock = patch.object(routines, 'LOCK', Path(tmp.name) / 'routines.lock')
        lock.start()
        self.addCleanup(lock.stop)
        self.store = {}
        load = patch.object(routines.config, 'load', side_effect=lambda: copy.deepcopy(self.store))
        save = patch.object(routines.config, 'save', side_effect=self._save)
        load.start()
        save.start()
        self.addCleanup(load.stop)
        self.addCleanup(save.stop)

    def _save(self, cfg):
        self.store.clear()
        self.store.update(copy.deepcopy(cfg))

    def _stored(self, **fields):
        self.store = {'routines': [{**_routine(**fields), 'last': fields.get('last', '')}]}


class Store(_Config):
    def test_add_and_load(self):
        self.assertTrue(routines.add('  Check   backups ', '0:05', 'L1', 'Asia/Dubai'))
        self.assertEqual(routines.load(), [_routine(title='Check backups', zone='Asia/Dubai')])
        self.assertEqual(self.store['routines'][0]['last'], '')

    def test_add_rejects(self):
        self.assertFalse(routines.add('  ', '00:05', 'L1'))
        self.assertFalse(routines.add('Check', '25:00', 'L1'))
        self.assertEqual(self.store, {})

    def test_garbage(self):
        self.store = {'routines': [
            5, {'title': 'A'}, {'title': 'A', 'time': 7},
            {'title': 'B', 'time': '7:30', 'zone': 'Nowhere/../x', 'rule': 'weekly', 'list': 3, 'last': 'soon'},
            {'title': 'Альфа', 'time': '23:59', 'rule': 'manual', 'last': '2026-11-23T00:05'},
        ]}
        self.assertEqual(routines.load(), [
            _routine(title='B', time='07:30', list=''),
            _routine(title='Альфа', time='23:59', rule='manual', list='', last=datetime(2026, 11, 23, 0, 5)),
        ])

    def test_not_a_list(self):
        self.store = {'routines': {}}
        self.assertEqual(routines.load(), [])

    def test_rule_change_keeps_last(self):
        self._stored(last='2026-11-24T00:05')
        self.assertTrue(routines.change(1, rule='daily'))
        self.assertEqual((self.store['routines'][0]['rule'], self.store['routines'][0]['last']),
                         ('daily', '2026-11-24T00:05'))

    def test_time_and_zone_change_reset_last(self):
        for fields in ({'time': '01:00'}, {'zone': 'Asia/Dubai'}):
            with self.subTest(fields):
                self._stored(last='2026-11-24T00:05')
                routines.change(1, **fields)
                self.assertEqual(self.store['routines'][0]['last'], '')

    def test_change_out_of_range(self):
        self._stored()
        before = copy.deepcopy(self.store)
        for n in (0, 2):
            with self.subTest(n):
                self.assertFalse(routines.change(n, rule='daily'))
        self.assertEqual(self.store, before)

    def test_remove(self):
        routines.add('A', '01:00', 'L1')
        routines.add('B', '02:00', 'L1')
        self.assertFalse(routines.remove(3))
        self.assertTrue(routines.remove(1))
        self.assertEqual([r['title'] for r in routines.load()], ['B'])

    def test_keeps_other_config(self):
        self.store = {'operator_name': 'me'}
        routines.add('A', '01:00', 'L1')
        self.assertEqual(self.store['operator_name'], 'me')


class Parse(unittest.TestCase):
    def _parse(self, text, default='L1'):
        return routines.parse(text, LISTS, default, date(2026, 11, 23))

    def test_title_and_time(self):
        self.assertEqual(self._parse('Check backups 00:05'),
                         ({'title': 'Check backups', 'time': '00:05', 'list': 'L1'}, None))

    def test_cyrillic_and_list(self):
        self.assertEqual(self._parse('0:05 Проверить Альфа #Список'),
                         ({'title': 'Проверить Альфа', 'time': '00:05', 'list': 'L2'}, None))

    def test_problems(self):
        cases = {
            'Check': 'Type one time, e.g. 00:05',
            'Check 22:00-23:00': 'Type one time, e.g. 00:05',
            'Check 25:00': 'No such time: 25:00',
            'Check 00:05 tomorrow': 'A routine takes a time, not a date',
            '00:05 #Todo': 'Type the reminder text',
            'Check 00:05 #Todo #Список': 'Use one #list',
            'Check 00:05 #Nope': 'No list #Nope',
            'Check ²2:05': 'Type one time, e.g. 00:05',
        }
        for text, problem in cases.items():
            with self.subTest(text):
                self.assertEqual(self._parse(text), (None, problem))

    def test_no_default_list(self):
        self.assertEqual(self._parse('Check 00:05', None), (None, 'Choose lists in settings'))

    def test_other_digits(self):
        self.assertEqual(self._parse('Check ٢٢:٠٥')[0]['time'], '22:05')

    def test_next_rule(self):
        self.assertEqual([routines.next_rule(r) for r in routines.RULES], ['daily', 'manual', 'shift'])


class Next(unittest.TestCase):
    def test_night_shift(self):
        self.assertEqual(routines.upcoming(_routine(), MON, SCHED), datetime(2026, 11, 24, 0, 5))

    def test_skips_days_off(self):
        self.assertEqual(routines.upcoming(_routine(), WED, SCHED), datetime(2026, 12, 1, 0, 5))

    def test_any_shift_counts(self):
        self.assertEqual(routines.upcoming(_routine(time='12:00'), WED, SCHED), datetime(2026, 11, 27, 12, 0))

    def test_shift_end_excluded_start_included(self):
        self.assertEqual(routines.upcoming(_routine(time='08:00'), MON, SCHED), datetime(2026, 11, 27, 8, 0))

    def test_vacation(self):
        s = replace(SCHED, vacations=((date(2026, 11, 23), date(2026, 11, 29)),))
        self.assertEqual(routines.upcoming(_routine(), MON, s), datetime(2026, 12, 1, 0, 5))

    def test_schedule_off(self):
        self.assertIsNone(routines.upcoming(_routine(), MON, replace(SCHED, enabled=False)))

    def test_daily_ignores_schedule(self):
        off = replace(SCHED, enabled=False)
        self.assertEqual(routines.upcoming(_routine(rule='daily'), WED, off), datetime(2026, 11, 26, 0, 5))

    def test_manual_never(self):
        self.assertIsNone(routines.upcoming(_routine(rule='manual'), MON, SCHED))

    def test_now_is_not_ahead(self):
        self.assertEqual(routines.soonest(_routine(), datetime(2026, 11, 24, 0, 5)), datetime(2026, 11, 25, 0, 5))

    def test_zone(self):
        cases = {
            datetime(2026, 11, 23, 12, 0): datetime(2026, 11, 23, 21, 5),
            datetime(2026, 7, 1, 12, 0): datetime(2026, 7, 1, 22, 5),
            datetime(2026, 10, 24, 23, 0): datetime(2026, 10, 25, 21, 5),
        }
        with patch.object(routines.zones, '_local', return_value=ZoneInfo('Europe/Berlin')):
            for now, moment in cases.items():
                with self.subTest(now):
                    self.assertEqual(routines.soonest(_routine(zone='Asia/Dubai'), now), moment)

    def test_pending(self):
        night = datetime(2026, 11, 24, 0, 5)
        items = [_routine(), _routine(last=night), _routine(last=datetime(2026, 11, 23, 0, 5)), _routine(rule='manual')]
        self.assertEqual(routines.pending(items, MON, SCHED), [(1, night), (3, night)])


class Plan(_Config):
    def _source(self, ok=True):
        source = Mock()
        source.add.return_value = ok
        return source

    def test_adds_once(self):
        routines.add('Проверить Альфа', '00:05', 'L1')
        source = self._source()
        self.assertEqual(routines.plan(source, MON, SCHED), 1)
        self.assertEqual(routines.plan(source, MON, SCHED), 0)
        source.add.assert_called_once_with('Проверить Альфа', 'L1', None, datetime(2026, 11, 24, 0, 5))
        self.assertEqual(self.store['routines'][0]['last'], '2026-11-24T00:05')

    def test_next_night_after_the_first(self):
        self._stored(last='2026-11-24T00:05')
        source = self._source()
        self.assertEqual(routines.plan(source, datetime(2026, 11, 24, 1, 0), SCHED), 1)
        source.add.assert_called_once_with('Check', 'L1', None, datetime(2026, 11, 25, 0, 5))

    def test_failure_keeps_last(self):
        self._stored()
        self.assertEqual(routines.plan(self._source(ok=False), MON, SCHED), 0)
        self.assertEqual(self.store['routines'][0]['last'], '')

    def test_plan_waits_its_turn(self):
        if routines.fcntl is None:
            self.skipTest('no file locks here')
        routines.add('Проверить Альфа', '00:05', 'L1')
        source = self._source()
        with routines._turn():
            self.assertEqual(routines.plan(source, MON, SCHED), 0)
        source.add.assert_not_called()
        self.assertEqual(routines.plan(source, MON, SCHED), 1)

    def test_manual_not_planned(self):
        self._stored(rule='manual')
        source = self._source()
        self.assertEqual(routines.plan(source, MON, SCHED), 0)
        source.add.assert_not_called()

    def test_remind(self):
        self._stored(rule='manual')
        source = self._source()
        night = datetime(2026, 11, 24, 0, 5)
        self.assertEqual(routines.remind(source, 1, MON), (night, None))
        self.assertEqual(routines.remind(source, 1, MON), (night, 'Already set'))
        source.add.assert_called_once_with('Check', 'L1', None, night)

    def test_remind_failure(self):
        self._stored(rule='manual')
        self.assertEqual(routines.remind(self._source(ok=False), 1, MON), (None, 'Could not add the reminder'))
        self.assertEqual(self.store['routines'][0]['last'], '')

    def test_remind_keeps_later_last(self):
        self._stored(last='2026-12-01T00:05')
        routines.remind(self._source(), 1, MON)
        self.assertEqual(self.store['routines'][0]['last'], '2026-12-01T00:05')


class Home(unittest.TestCase):
    def _plan(self, source):
        with patch.object(main_screen.registry, 'active', return_value=source) as active, \
             patch.object(main_screen.routines, 'plan') as plan:
            main_screen._plan()
        active.assert_called_once_with('tasks')
        return plan

    def test_plans_with_ready_source(self):
        source = Mock()
        source.available.return_value = True
        self._plan(source).assert_called_once_with(source)

    def test_skips_unavailable_source(self):
        source = Mock()
        source.available.return_value = False
        self._plan(source).assert_not_called()

    def test_skips_without_source(self):
        self._plan(None).assert_not_called()

    def test_frame_plans_before_blocks(self):
        steps = Mock()
        steps.block.return_value = []
        with patch.object(main_screen, '_plan', steps.plan), patch.object(main_screen, '_block', steps.block), \
             patch.object(main_screen, 'home_order', return_value=['reminders']), \
             patch.object(main_screen, 'operator_name', return_value=''), \
             patch.object(main_screen, 'pending_update', return_value=False), \
             patch.object(main_screen.archives, 'count', return_value=0), \
             patch.object(main_screen, '_logo', return_value=[]):
            main_screen._frame()
        self.assertEqual(steps.mock_calls, [call.plan(), call.block('reminders')])


if __name__ == '__main__':
    unittest.main()
