import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from screens import main_screen as main
from ui.interface import visible


class _Stop(Exception):
    pass


def _source(key):
    return SimpleNamespace(KIND=main.registry.BLOCKS[key])


from datetime import date, datetime
from unittest.mock import Mock

NOW = datetime(2026, 11, 22, 12, 0)


def _task(title, due, all_day=False, list_id='L1'):
    return {'id': title, 'title': title, 'due': due, 'all_day': all_day, 'list': list_id, 'done': False}


class Bar(unittest.TestCase):
    def _bar(self, found, duty=None, source=True, end=None, finished=()):
        status = SimpleNamespace(on=True, shift=SimpleNamespace(end=end)) if end else None
        found_source = SimpleNamespace(KEY='remindctl', NAME='Reminders', available=lambda: True,
                                       items=lambda: found) if source else None
        with patch.object(main, '_plan') as self.planned, \
             patch.object(main.schedule, 'load', return_value=SimpleNamespace(status=lambda now: status)), \
             patch.object(main.registry, 'active', return_value=found_source), \
             patch.object(main.sources, 'selected', return_value=['L1']), \
             patch.object(main, 'finished_today', return_value=list(finished)), \
             patch.object(main, 'duty_line', return_value=duty), \
             patch.object(main.swiftbar, 'render', side_effect=lambda *a: a):
            return main.bar_frame(NOW)

    def test_calm(self):
        self.assertEqual(self._bar([_task('Alpha', datetime(2026, 11, 22, 13, 0))]),
                         (False, '', False, '', [('today', [('○ 13:00 Alpha', False, ('done', 'Alpha'))])]))

    def test_soon_in_title(self):
        self.assertEqual(self._bar([_task('Alpha', datetime(2026, 11, 22, 12, 30))])[1:3], ('12:30 Alpha', False))
        self.assertEqual(self._bar([_task('Alpha', datetime(2026, 11, 22, 12, 31))])[1], '')

    def test_overdue_wins(self):
        todo = _task('Todo', datetime(2026, 11, 22, 11, 0))
        _, title, alert, _, groups = self._bar([_task('Alpha', datetime(2026, 11, 22, 12, 10)), todo])
        self.assertEqual((title, alert), ('11:00 Todo', True))
        self.assertEqual(groups, [('overdue', [(f'○ {main.when(todo, NOW)} Todo', True, ('done', 'Todo'))]),
                                  ('today', [('○ 12:10 Alpha', False, ('done', 'Alpha'))])])

    def test_overdue_all_day(self):
        self.assertEqual(self._bar([_task('Todo', datetime(2026, 11, 21), all_day=True)])[1:3], ('Todo', True))

    def test_all_day_today_stays_calm(self):
        self.assertEqual(self._bar([_task('Todo', datetime(2026, 11, 22), all_day=True)])[1:3], ('', False))

    def test_days_grouped(self):
        groups = self._bar([_task('Alpha', datetime(2026, 11, 23, 9, 0)), _task('Todo', datetime(2026, 11, 24, 9, 0))])[4]
        self.assertEqual([head for head, _ in groups], ['tomorrow', main.day_label(date(2026, 11, 24), NOW.date())])

    def test_on_duty_groups_shift(self):
        on, _, _, _, groups = self._bar([_task('Alpha', datetime(2026, 11, 22, 23, 0)),
                                         _task('Todo', datetime(2026, 11, 23, 9, 0))],
                                        end=datetime(2026, 11, 23, 8, 0))
        self.assertTrue(on)
        self.assertEqual([head for head, _ in groups], ['this shift · until 08:00', 'tomorrow'])

    def test_done_today_last(self):
        done = dict(_task('Todo', None), done=True, finished=datetime(2026, 11, 22, 11, 5))
        groups = self._bar([_task('Alpha', datetime(2026, 11, 22, 13, 0))], finished=[done])[4]
        self.assertEqual(groups[-1], ('done today', [('✓ 11:05 Todo', False, ('undo', 'Todo'))]))

    def test_all_day_row_has_no_time(self):
        groups = self._bar([_task('Todo', datetime(2026, 11, 23), all_day=True)])[4]
        self.assertEqual(groups, [('tomorrow', [('○ Todo', False, ('done', 'Todo'))])])

    def test_duty_without_colors(self):
        self.assertEqual(self._bar([], duty='\033[2m● OFF DUTY\033[0m')[3], '● OFF DUTY')

    def test_limit_and_undated(self):
        found = [_task(f'Alpha {i}', datetime(2026, 11, 23, 9, i)) for i in range(12)] + [_task('Todo', None)]
        rows = [row for _, group in self._bar(found)[4] for row in group]
        self.assertEqual(len(rows), main.BAR_ROWS)
        self.assertFalse(any('Todo' in text for text, *_ in rows))

    def test_hidden_lists_skipped(self):
        self.assertEqual(self._bar([_task('Alpha', datetime(2026, 11, 23, 9, 0), list_id='L2')])[4], [])

    def test_unreadable(self):
        self.assertEqual(self._bar(None)[4], [('', [('Could not read Reminders', True, None)])])

    def test_no_source(self):
        self.assertEqual(self._bar([], source=False), (False, '', False, '', []))

    def test_plans_routines(self):
        self._bar([])
        self.planned.assert_called_once_with()


class BarToggle(unittest.TestCase):
    def _toggle(self, action, task_id, found=(), finished=()):
        self.source = SimpleNamespace(KEY='remindctl', available=lambda: True, items=lambda: list(found),
                                      complete=Mock(return_value=True), reopen=Mock(return_value=True))
        with patch.object(main.registry, 'active', return_value=self.source), \
             patch.object(main.sources, 'selected', return_value=['L1']), \
             patch.object(main, 'finished_today', return_value=list(finished)):
            return main.bar_toggle(action, task_id, NOW)

    def test_done(self):
        self.assertTrue(self._toggle('done', 'Alpha', found=[_task('Alpha', None)]))
        self.source.complete.assert_called_once_with('Alpha')

    def test_done_ignores_unknown(self):
        self.assertFalse(self._toggle('done', 'Todo', found=[_task('Alpha', None)]))
        self.source.complete.assert_not_called()

    def test_done_ignores_hidden_list(self):
        self.assertFalse(self._toggle('done', 'Alpha', found=[_task('Alpha', None, list_id='L2')]))
        self.source.complete.assert_not_called()

    def test_undo(self):
        self.assertTrue(self._toggle('undo', 'Todo', finished=[dict(_task('Todo', None), done=True)]))
        self.source.reopen.assert_called_once_with('Todo')

    def test_undo_ignores_unknown(self):
        self.assertFalse(self._toggle('undo', 'Alpha', finished=[dict(_task('Todo', None), done=True)]))
        self.source.reopen.assert_not_called()


class Dispatch(unittest.TestCase):
    def _run(self, *inputs, loaded=True, query=None):
        with patch.object(main, '_frame', return_value=[]), \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main, 'pause'), \
             patch.object(main.archives, 'is_loaded', return_value=loaded), \
             patch.object(main.archives, 'missing', return_value=[]), \
             patch.object(main, 'read_command', side_effect=[*inputs, _Stop()]) as self.read, \
             patch.object(main, 'search_screen') as search, \
             patch('core.commands.settings_screen') as settings:
            with self.assertRaises(_Stop):
                main.main_screen(query=query)
        return search, settings

    def test_start_query_searches_first(self):
        search, settings = self._run(query='nginx timeout')
        search.assert_called_once_with('nginx timeout')
        settings.assert_not_called()
        self.assertEqual(self.read.call_count, 1)

    def test_start_query_then_prompt(self):
        search, _ = self._run('redis', query='nginx')
        self.assertEqual([c.args for c in search.call_args_list], [('nginx',), ('redis',)])

    def test_start_command(self):
        search, settings = self._run(query='s')
        settings.assert_called_once()
        search.assert_not_called()

    def test_start_query_without_archive(self):
        search, _ = self._run(query='nginx', loaded=False)
        search.assert_not_called()

    def test_no_start_query(self):
        for query in (None, ''):
            with self.subTest(repr(query)):
                search, settings = self._run(query=query)
                search.assert_not_called()
                settings.assert_not_called()

    def test_home_from_start_query(self):
        with patch.object(main, '_frame', return_value=[]), \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main.archives, 'is_loaded', return_value=True), \
             patch.object(main, 'read_command', side_effect=['redis', _Stop()]), \
             patch.object(main, 'search_screen', side_effect=[main.Home(), None]) as search:
            with self.assertRaises(_Stop):
                main.main_screen(query='nginx')
        self.assertEqual([c.args for c in search.call_args_list], [('nginx',), ('redis',)])

    def test_query_goes_to_search(self):
        search, settings = self._run('nginx')
        search.assert_called_once_with('nginx')
        settings.assert_not_called()

    def test_command_runs_without_search(self):
        search, settings = self._run('s')
        settings.assert_called_once()
        search.assert_not_called()

    def test_empty_input_only_redraws(self):
        search, settings = self._run('')
        search.assert_not_called()
        settings.assert_not_called()

    def test_no_archive_no_search(self):
        search, _ = self._run('nginx', loaded=False)
        search.assert_not_called()

    def test_several_inputs_in_a_row(self):
        search, settings = self._run('s', 'nginx', '', 'redis')
        self.assertEqual([c.args for c in search.call_args_list], [('nginx',), ('redis',)])
        settings.assert_called_once()

    def test_back_does_nothing(self):
        search, settings = self._run('b', 'back', 'B')
        search.assert_not_called()
        settings.assert_not_called()

    def test_home_from_inner_screen(self):
        with patch.object(main, '_frame', return_value=[]), \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main.archives, 'is_loaded', return_value=True), \
             patch.object(main, 'read_command', side_effect=['nginx', 'redis', _Stop()]), \
             patch.object(main, 'search_screen', side_effect=[main.Home(), None]) as search:
            with self.assertRaises(_Stop):
                main.main_screen()
        self.assertEqual([c.args for c in search.call_args_list], [('nginx',), ('redis',)])

    def test_home_on_main_redraws(self):
        with patch.object(main, '_frame', return_value=[]) as frame, \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print'), \
             patch.object(main, 'read_command', side_effect=[main.Home(), _Stop()]):
            with self.assertRaises(_Stop):
                main.main_screen()
        self.assertEqual(frame.call_count, 2)


class Frame(unittest.TestCase):
    def test_frame_ready_before_clear(self):
        calls = []
        with patch.object(main, '_frame', side_effect=lambda: calls.append('frame') or []), \
             patch.object(main, 'clear_screen', side_effect=lambda: calls.append('clear')), \
             patch('builtins.print'), \
             patch.object(main, 'read_command', side_effect=_Stop()):
            with self.assertRaises(_Stop):
                main.main_screen()
        self.assertEqual(calls, ['frame', 'clear'])

    def test_start_query_draws_fresh_frame(self):
        with patch.object(main, '_frame', return_value=['fresh']) as frame, \
             patch.object(main, 'clear_screen'), \
             patch('builtins.print') as out, \
             patch.object(main.archives, 'is_loaded', return_value=True), \
             patch.object(main, 'search_screen'), \
             patch.object(main, 'read_command', side_effect=_Stop()):
            with self.assertRaises(_Stop):
                main.main_screen('stale', 'nginx')
        frame.assert_called_once()
        self.assertEqual([c.args for c in out.call_args_list], [('fresh',)])


class Width(unittest.TestCase):
    def test_lines_fit_terminal(self):
        long = 'x' * 100
        with patch.object(main, '_logo', return_value=[]), \
             patch.object(main, 'operator_name', return_value=long), \
             patch.object(main.archives, 'count', return_value=0), \
             patch.object(main, 'duty_line', return_value=long), \
             patch.object(main.registry, 'block', side_effect=_source), \
             patch.object(main, 'agenda', return_value=[long]), \
             patch.object(main, 'summary', return_value=[long]), \
             patch.object(main, 'pending_update', return_value=False), \
             patch('shutil.get_terminal_size', return_value=os.terminal_size((30, 24))):
            lines = main._frame()
        self.assertTrue(lines)
        self.assertTrue(all(len(visible(line)) <= 29 for line in lines))


class Blocks(unittest.TestCase):
    def _frame(self, order, duty='● ON DUTY'):
        with patch.object(main, '_logo', return_value=[]), \
             patch.object(main, 'operator_name', return_value=''), \
             patch.object(main.archives, 'count', return_value=0), \
             patch.object(main, 'pending_update', return_value=False), \
             patch.object(main, 'home_order', return_value=order), \
             patch.object(main.registry, 'block', side_effect=_source), \
             patch.object(main, 'agenda', return_value=['◇ Standup']), \
             patch.object(main, 'duty_line', return_value=duty), \
             patch.object(main, 'summary', return_value=['○ Buy milk']):
            return main._frame()[1:]

    def test_default_order(self):
        lines = self._frame(['calendar', 'schedule', 'reminders'])
        self.assertEqual([l for l in lines if l], ['◇ Standup', '● ON DUTY', '○ Buy milk'])

    def test_custom_order(self):
        lines = self._frame(['schedule', 'reminders', 'calendar'])
        self.assertEqual([l for l in lines if l], ['● ON DUTY', '○ Buy milk', '◇ Standup'])

    def test_empty_block_no_gap(self):
        lines = self._frame(['calendar', 'schedule', 'reminders'], duty='')
        self.assertEqual(lines, ['', '◇ Standup', '', '○ Buy milk', ''])


class Route(unittest.TestCase):
    def _block(self, key, source=None):
        with patch.object(main.registry, 'block', return_value=source) as self.found, \
             patch.object(main, 'agenda', return_value=['event']) as self.agenda, \
             patch.object(main, 'summary', return_value=['task']) as self.summary, \
             patch.object(main, 'duty_line', return_value=self.duty):
            return main._block(key)

    def setUp(self):
        self.duty = '● ON DUTY'

    def test_calendar_shows_agenda(self):
        source = _source('calendar')
        self.assertEqual(self._block('calendar', source), ['event'])
        self.found.assert_called_once_with('calendar')
        self.agenda.assert_called_once_with(source)
        self.summary.assert_not_called()

    def test_reminders_show_summary(self):
        source = _source('reminders')
        self.assertEqual(self._block('reminders', source), ['task'])
        self.summary.assert_called_once_with(source)
        self.agenda.assert_not_called()

    def test_kind_picks_view(self):
        self.assertEqual(self._block('calendar', SimpleNamespace(KIND='tasks')), ['task'])

    def test_no_source_no_block(self):
        self.assertEqual(self._block('calendar'), [])
        self.agenda.assert_not_called()
        self.summary.assert_not_called()

    def test_schedule_skips_sources(self):
        self.assertEqual(self._block('schedule'), ['● ON DUTY'])
        self.found.assert_not_called()

    def test_empty_schedule(self):
        self.duty = ''
        self.assertEqual(self._block('schedule'), [])
