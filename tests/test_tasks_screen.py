import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from screens import tasks_screen
from ui.interface import visible

NOW = datetime(2026, 11, 22, 21, 0)
WIDE = os.terminal_size((200, 50))


def _task(title, done=False, finished=None, list_id='L1'):
    return {'id': title, 'title': title, 'due': None, 'all_day': False, 'list': list_id, 'done': done,
            'finished': finished, 'list_name': '', 'notes': '', 'place': ''}


class DoneToday(unittest.TestCase):
    def _frame(self, finished):
        with mock.patch('shutil.get_terminal_size', return_value=WIDE):
            lines = tasks_screen._frame(SimpleNamespace(NAME='Reminders'), ['L1'], [('Work', [_task('Alpha')])],
                                        NOW, finished)
        return [visible(line) for line in lines]

    def test_done_today_at_bottom(self):
        lines = self._frame([_task('Альфа', done=True, finished=datetime(2026, 11, 22, 20, 14))])
        self.assertIn('  2 ✓ Альфа · 20:14', lines)
        self.assertLess(lines.index('  1 ○ Alpha'), lines.index('done today'))

    def test_undo_hint_only_with_done(self):
        done = [_task('Альфа', done=True, finished=datetime(2026, 11, 22, 20, 14))]
        self.assertIn('done/undo', '\n'.join(self._frame(done)))
        self.assertNotIn('undo', '\n'.join(self._frame([])))


class Toggle(unittest.TestCase):
    def _toggle(self, task, ok=True):
        self.source = SimpleNamespace(complete=mock.Mock(return_value=ok), reopen=mock.Mock(return_value=ok))
        with mock.patch.object(tasks_screen, 'haptic'), \
             mock.patch.object(tasks_screen, '_refresh_bar') as self.refreshed, \
             mock.patch.object(tasks_screen, 'error') as self.error:
            return tasks_screen._toggle(self.source, task)

    def test_open_completes(self):
        self.assertTrue(self._toggle(_task('Alpha')))
        self.source.complete.assert_called_once_with('Alpha')
        self.source.reopen.assert_not_called()

    def test_done_reopens(self):
        self.assertTrue(self._toggle(_task('Todo', done=True)))
        self.source.reopen.assert_called_once_with('Todo')
        self.source.complete.assert_not_called()

    def test_failed_reopen_reported(self):
        self.assertFalse(self._toggle(_task('Todo', done=True), ok=False))
        self.error.assert_called_once_with('Could not reopen: Todo')
        self.refreshed.assert_not_called()

    def test_change_refreshes_menu_bar(self):
        self._toggle(_task('Alpha'))
        self.refreshed.assert_called_once()


class FinishedToday(unittest.TestCase):
    ITEMS = [
        _task('Alpha', done=True, finished=datetime(2026, 11, 22, 10, 0)),
        _task('Todo', done=True, finished=datetime(2026, 11, 21, 22, 0)),
        _task('Альфа', done=True, finished=datetime(2026, 11, 22, 11, 0), list_id='L2'),
        _task('Open'),
        _task('Old', done=True),
    ]

    def _found(self, status=None, read=True):
        source = SimpleNamespace(completed=lambda: self.ITEMS) if read else SimpleNamespace()
        with mock.patch.object(tasks_screen.schedule, 'load', return_value=SimpleNamespace(status=lambda now: status)):
            return [t['id'] for t in tasks_screen.finished_today(source, ['L1'], NOW)]

    def test_since_midnight(self):
        self.assertEqual(self._found(), ['Alpha'])

    def test_night_shift_keeps_evening(self):
        status = SimpleNamespace(on=True, shift=SimpleNamespace(start=datetime(2026, 11, 21, 20, 0)))
        self.assertEqual(self._found(status), ['Todo', 'Alpha'])

    def test_source_without_history(self):
        self.assertEqual(self._found(read=False), [])


class Summary(unittest.TestCase):
    def _summary(self, done, ready=True, rest=0):
        source = SimpleNamespace(KEY='remindctl', SHOWN=3, available=lambda: ready)
        with mock.patch.object(tasks_screen, 'open_tasks', return_value=([_task('Alpha')], rest)), \
             mock.patch.object(tasks_screen, 'finished_today', return_value=done) as self.read, \
             mock.patch.object(tasks_screen.sources, 'option', return_value=3), \
             mock.patch.object(tasks_screen.sources, 'selected', return_value=['L1']):
            return [visible(line) for line in tasks_screen.summary(source, NOW)]

    def test_counts_done_today(self):
        lines = self._summary([_task('Todo', done=True), _task('Альфа', done=True)])
        self.assertEqual(lines[-1], '✓ 2 done today')

    def test_more_and_done_share_line(self):
        lines = self._summary([_task('Todo', done=True), _task('Альфа', done=True)], rest=48)
        self.assertEqual(lines[-1], '+48 more · ✓ 2 done today')
        self.assertEqual(len(lines), 2)

    def test_nothing_done_no_line(self):
        self.assertFalse(any('done today' in line for line in self._summary([])))

    def test_offline_skips_history(self):
        self._summary([_task('Todo', done=True)], ready=False)
        self.read.assert_not_called()


class Narrow(unittest.TestCase):
    def test_summary_keeps_time(self):
        task = dict(_task('Позвонить поставщику по поводу договора и счетов'), due=datetime(2026, 11, 22, 23, 0),
                    list_name='work')
        source = SimpleNamespace(KEY='remindctl', SHOWN=3, available=lambda: False)
        with mock.patch.object(tasks_screen, 'open_tasks', return_value=([task], 0)), \
             mock.patch.object(tasks_screen.sources, 'option', return_value=3), \
             mock.patch('shutil.get_terminal_size', return_value=os.terminal_size((41, 24))):
            line = visible(tasks_screen.summary(source, NOW)[0])
        self.assertTrue(line.endswith('… · today 23:00'))
        self.assertLessEqual(len(line), 40)
