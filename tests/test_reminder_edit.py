import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest import mock

from core.sources import cli, remindctl
from screens import tasks_screen

LISTS = [{'id': 'L1', 'title': 'Work'}, {'id': 'L5', 'title': 'Pets'}]


def _task():
    return {'id': 'a', 'title': 'Alpha', 'notes': '', 'list': 'L1', 'list_name': 'Work', 'due': None, 'all_day': False}


class RemindctlEdit(unittest.TestCase):
    def _args(self, **found):
        with mock.patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            self.assertTrue(remindctl.edit('a', **found))
        return list(run.call_args.args[1:]) if run.called else None

    def test_due_and_alarm(self):
        self.assertEqual(self._args(due=datetime(2026, 10, 11, 18, 0), alarm=None),
                         ['edit', 'a', '--due', '2026-10-11 18:00', '--clear-alarm'])

    def test_clear_due_and_all_day(self):
        self.assertEqual(self._args(due=None), ['edit', 'a', '--clear-due'])
        self.assertEqual(self._args(due=date(2026, 10, 20)), ['edit', 'a', '--due', '2026-10-20'])

    def test_alarm(self):
        self.assertEqual(self._args(alarm=datetime(2026, 10, 11, 17, 50)),
                         ['edit', 'a', '--alarm', '2026-10-11 17:50'])

    def test_nothing(self):
        self.assertIsNone(self._args())

    def test_move(self):
        with mock.patch.object(remindctl.cli, 'run_ok', return_value=True) as run:
            remindctl.move('a', 'L5')
        self.assertEqual(run.call_args.args, ('remindctl', 'edit', 'a', '--list-id', 'L5'))

    def test_alarm_read(self):
        stamp = '2026-10-11T17:50:00Z'
        task = remindctl.parse_items([{'id': 'a', 'title': 'Alpha', 'alarmDate': stamp}])[0]
        self.assertEqual(task['alarm'], cli.parse_time(stamp))
        self.assertIsNone(remindctl.parse_items([{'id': 'a', 'title': 'Alpha'}])[0]['alarm'])


class ScreenEdit(unittest.TestCase):
    def _edit(self, texts, task=None, lists=LISTS, edit=True, move=True):
        task = task or _task()
        source = SimpleNamespace(lists=lambda: lists, edit=mock.Mock(return_value=edit),
                                 move=mock. Mock(return_value=move))
        with mock.patch.object(tasks_screen.editor, 'edit_text', side_effect=texts) as self.editor, \
             mock.patch.object(tasks_screen, 'error') as self.error, \
             mock.patch.object(tasks_screen, 'haptic'), \
             mock.patch.object(tasks_screen, '_refresh_bar'):
            tasks_screen._edit(source, task)
        return source, task

    def test_saves_and_moves(self):
        source, task = self._edit(['Alpha 20-10-2030 #Pets'])
        source.edit.assert_called_once_with('a', due=date(2030, 10, 20))
        source.move.assert_called_once_with('a', 'L5')
        self.assertEqual((task['list_name'], task['due'], task['all_day']), ('Pets', datetime(2030, 10, 20), True))
        self.error.assert_not_called()

    def test_only_move(self):
        source, _ = self._edit(['Alpha #Pets'])
        source.edit.assert_not_called()
        source.move.assert_called_once_with('a', 'L5')

    def test_bad_text_reopens_with_it(self):
        source, _ = self._edit(['Alpha 25:00', ''])
        self.assertEqual(self.editor.call_args_list[1].args[0], 'Alpha 25:00')
        self.assertEqual([c.args[0] for c in self.error.call_args_list],
                         ['No such time: 25:00', 'Empty text — edit cancelled'])
        source.edit.assert_not_called()

    def test_move_fails_keeps_rest(self):
        source, task = self._edit(['Beta #Pets'], move=False)
        self.error.assert_called_once_with('Could not move to #Pets, move it in Reminders')
        self.assertEqual((task['title'], task['list_name']), ('Beta', 'Work'))

    def test_save_fails(self):
        source, task = self._edit(['Beta #Pets'], edit=False)
        self.error.assert_called_once_with('Could not save the reminder')
        source.move.assert_not_called()
        self.assertEqual(task['title'], 'Alpha')

    def test_lists_unreadable(self):
        self._edit([], lists=None)
        self.error.assert_called_once_with('Could not read the lists')
        self.editor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
