import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from screens import keeper_screen as screen

CASE = {'text': 'Relay fault\nReplace fuse F12', 'archive': 'Vault'}
WIDTH = 200


def _state(question, **extra):
    state = {'question': question, 'kind': 'reply', 'reply': 'Noted.', 'quotes': [], 'sources': [], 'cited': 0,
             'archive': True, 'lookup': False, 'terms': '', 'online': True, 'via': 'local', 'links': [],
             'missing': False}
    state.update(extra)
    return state


class Wide(unittest.TestCase):
    def run_screen(self, commands, answers):
        with mock.patch.object(screen, '_redraw', return_value=('local', 0)), \
             mock.patch.object(screen, '_drop_nav'), \
             mock.patch.object(screen, '_print_answer'), \
             mock.patch.object(screen, '_nav'), \
             mock.patch.object(screen, 'haptic'), \
             mock.patch.object(screen, 'Spinner'), \
             mock.patch.object(screen.keeper, 'active', return_value={'slot': 'local'}), \
             mock.patch.object(screen, 'read_command', side_effect=commands), \
             mock.patch.object(screen, '_ask', side_effect=answers) as ask:
            screen.keeper_screen(CASE)
        return ask.call_args_list

    def test_slash_asks_archive_after_miss(self):
        calls = self.run_screen(['what fuse', '/', 'b'],
                                [_state('what fuse', missing=True, archive=False), _state('what fuse')])
        self.assertEqual([c.args[0] for c in calls], ['what fuse', 'what fuse'])
        self.assertIs(calls[0].args[3], CASE)
        self.assertIsNone(calls[1].args[3])

    def test_slash_works_once(self):
        calls = self.run_screen(['what fuse', '/', '/', 'b'], [_state('what fuse', missing=True), _state('what fuse')])
        self.assertEqual([c.args[0] for c in calls], ['what fuse', 'what fuse'])

    def test_slash_without_miss_is_short(self):
        calls = self.run_screen(['what fuse', '/', 'b'], [_state('what fuse')])
        self.assertEqual([c.args[0] for c in calls], ['what fuse'])


class Note(unittest.TestCase):
    def printed(self, state):
        out = io.StringIO()
        with mock.patch.object(screen, '_width', return_value=WIDTH), redirect_stdout(out):
            screen._print_answer(dict(state, start=2))
        return out.getvalue()

    def test_shown_when_missing(self):
        out = self.printed(_state('q', reply='Not in this record.', missing=True, archive=False))
        self.assertIn('Not in this record.', out)
        self.assertIn(screen.LINES['wide'], out)

    def test_hidden_when_found(self):
        self.assertNotIn(screen.LINES['wide'], self.printed(_state('q')))

    def test_after_shown_below_quotes(self):
        out = self.printed(_state('q', quotes=['Reset relay R1.'], after=['Alarm A7 may appear.']))
        self.assertLess(out.index('Reset relay R1.'), out.index(screen.LINES['after']))
        self.assertLess(out.index(screen.LINES['after']), out.index('Alarm A7 may appear.'))

    def test_after_hidden_when_empty(self):
        self.assertNotIn(screen.LINES['after'], self.printed(_state('q', after=[])))

    def test_calculation_above_steps(self):
        calc = {'rows': [('Panel total', '1 280.18'), ('report total', '1 280.20')], 'diff': '0.02',
                'target': 1, 'plan': 'Change «Panel total»: add 0.02.', 'basis': 'as the report total'}
        out = self.printed(_state('q', reply='1. Add 0.02.', calc=calc))
        lines = out.splitlines()
        marked = [ln for ln in lines if screen.LINES['correct'] in ln]
        self.assertEqual(len(marked), 1)
        self.assertIn('1 280.20', marked[0])
        self.assertIn('0.02', next(ln for ln in lines if screen.LINES['diff'] in ln))
        self.assertLess(out.index(screen.LINES['calc']), out.index('Change «Panel total»'))
        self.assertLess(out.index('Change «Panel total»'), out.index('1. Add 0.02.'))
        self.assertIn(f"{screen.LINES['basis']} «as the report total»", out)
        self.assertNotIn(screen.LINES['unchecked'], out)

    def test_unknown_side_has_no_mark(self):
        calc = {'rows': [('a', '1.10'), ('b', '1.12')], 'diff': '0.02', 'target': None, 'plan': 'Unknown.',
                'basis': ''}
        out = self.printed(_state('q', reply='1. Check.', calc=calc))
        self.assertNotIn(screen. LINES['correct'], out)
        self.assertNotIn(screen.LINES['basis'], out)

    def test_calculation_kept_when_steps_hidden(self):
        calc = {'rows': [('a', '1.10'), ('b', '1.12')], 'diff': '0.02', 'target': 0, 'plan': 'Subtract.',
                'basis': ''}
        out = self.printed(_state('q', reply='', archive=False, calc=calc))
        self.assertIn('Subtract.', out)
        self.assertIn(screen.LINES['unchecked'], out)
        self.assertNotIn(screen.LINES['silent'], out)


class Gap(unittest.TestCase):
    def lines(self, state):
        out = io.StringIO()
        with mock.patch.object(screen, '_redraw', return_value=('local', 0)), \
             mock.patch.object(screen, '_drop_nav'), \
             mock.patch.object(screen, '_nav'), \
             mock.patch.object(screen, 'haptic'), \
             mock.patch.object(screen, 'Spinner'), \
             mock.patch.object(screen.keeper, 'active', return_value={'slot': 'local'}), \
             mock.patch.object(screen.keeper, 'has_server', return_value=True), \
             mock.patch.object(screen, 'read_command', side_effect=['what fuse', 'b']), \
             mock.patch.object(screen, '_ask', return_value=state), \
             mock.patch.object(screen, '_width', return_value=WIDTH), \
             redirect_stdout(out):
            screen.keeper_screen(CASE)
        return out.getvalue().split('\n')

    def test_one_blank_line_before_answer(self):
        self.assertEqual(self.lines(_state('what fuse'))[:2], ['', '  Noted.'])

    def test_switch_note_then_blank_then_answer(self):
        lines = self.lines(_state('what fuse', via='server'))
        self.assertEqual(lines[0], '')
        self.assertIn(screen.LINES['to_server'], lines[1])
        self.assertEqual(lines[2:4], ['', '  Noted.'])

    def test_short_question_one_blank_line(self):
        with mock.patch.object(screen.keeper, 'active', return_value=None):
            out = io.StringIO()
            with mock.patch.object(screen, '_redraw', return_value=(None, 0)), \
                 mock.patch.object(screen, '_drop_nav'), mock.patch.object(screen, '_nav'), \
                 mock.patch.object(screen, 'haptic'), \
                 mock.patch.object(screen, 'read_command', side_effect=['ab', 'b']), \
                 mock.patch.object(screen, '_width', return_value=WIDTH), redirect_stdout(out):
                screen.keeper_screen(CASE)
        lines = out.getvalue().split('\n')
        self.assertEqual(lines[0], '')
        self.assertIn(screen.LINES['short'], lines[1])


if __name__ == '__main__':
    unittest.main()
