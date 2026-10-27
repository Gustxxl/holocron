import json
import unittest
from unittest import mock
import urllib.error
from decimal import Decimal

from core import keeper

RELAY = {'text': 'Relay fault on orbit sensor\nReplace fuse F12\nCheck the harness', 'archive': 'Vault'}
GUIDE = {'text': 'Orbit manual\nSee [Setup guide](https://example.com/setup) first\n'
                 'Old ticket https://example.com/t/1', 'archive': 'Vault'}
NOTE = {'text': 'Routine note about lunch', 'archive': 'Vault'}
CASES = [RELAY, NOTE, GUIDE]
CONN = {'slot': 'local', 'url': 'http://x', 'model': 'm'}


class Reply(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(keeper, 'active', return_value=CONN)
        patch.start()
        self.addCleanup(patch.stop)
        self.chat = mock.patch.object(keeper, '_chat').start()
        self.addCleanup(mock.patch.stopall)

    def run_reply(self, plan, answers, message='relay fault again', past=None, records=(), focus=None):
        self.chat.side_effect = [plan, *answers]
        return keeper.reply(message, past or [], CASES, records, focus)

    def test_answer_from_record(self):
        out = self.run_reply({'terms': ['relay', 'fault']},
                             [{'reply': 'Replace the fuse [1].', 'used': [1], 'quotes': ['Replace fuse F12']}])
        self.assertTrue(out['archive'])
        self.assertEqual(out['sources'][0], RELAY)
        self.assertEqual(out['cited'], 1)
        self.assertEqual(out['quotes'], ['Replace fuse F12'])

    def test_small_talk_replies(self):
        out = self.run_reply({'terms': []}, [{'reply': 'Holocron is open.', 'used': []}], message='hello')
        self.assertEqual(out['reply'], 'Holocron is open.')
        self.assertFalse(out['lookup'])
        self.assertEqual(out['sources'], [])

    def test_nothing_found_still_replies(self):
        out = self.run_reply({'terms': ['quasar']}, [{'reply': 'No record on this. What system?', 'used': []}],
                             message='quasar drift')
        self.assertEqual(out['reply'], 'No record on this. What system?')
        self.assertTrue(out['lookup'])
        self.assertFalse(out['archive'])

    def test_history_passed(self):
        past = [{'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': json.dumps({'reply': 'Open.'})}]
        self.run_reply({'terms': []}, [{'reply': 'Noted.', 'used': []}], message='thanks', past=past)
        self.assertEqual(self.chat.call_args_list[1].args[2], past)
        self.assertIn('Keeper: Open.', self.chat.call_args_list[0].args[1])

    def test_invented_number_rejected(self):
        bad = {'reply': 'Replace fuse F99 [1].', 'used': [1]}
        out = self.run_reply({'terms': ['relay', 'fault']}, [bad, bad])
        self.assertEqual(out['reply'], '')
        self.assertIn(RELAY, out['sources'])

    def test_invented_number_retried(self):
        bad = {'reply': 'Replace fuse F99 [1].', 'used': [1]}
        good = {'reply': 'Replace fuse F12 [1].', 'used': [1]}
        out = self.run_reply({'terms': ['relay', 'fault']}, [bad, good])
        self.assertEqual(out['reply'], 'Replace fuse F12 [1].')

    def test_invented_link_rejected(self):
        bad = {'reply': 'See https://example.com/fix', 'used': []}
        out = self.run_reply({'terms': []}, [bad, bad], message='where is the fix')
        self.assertEqual(out['reply'], '')

    def test_fake_quote_dropped(self):
        out = self.run_reply({'terms': ['relay', 'fault']},
                             [{'reply': 'Fuse [1].', 'used': [1], 'quotes': ['Swap the whole board now']}])
        self.assertEqual(out['quotes'], [])

    def test_refers_to_shown_record(self):
        out = self.run_reply({'terms': [], 'records': [1]},
                             [{'reply': 'It names a fuse [1].', 'used': [1]}],
                             message='what about the first one', records=[RELAY])
        self.assertEqual(out['sources'], [RELAY])
        self.assertIn('Replace fuse F12', self.chat.call_args_list[1].args[1])

    def test_ungrounded_terms_dropped(self):
        out = self.run_reply({'terms': ['invented', 'relay']}, [{'reply': 'Fuse [1].', 'used': [1]}],
                             message='relay trouble')
        self.assertEqual(out['terms'], 'relay')

    def test_record_reference_is_not_a_number(self):
        out = self.run_reply({'terms': ['relay', 'fault']}, [{'reply': 'See [1] and [2].', 'used': [1]}])
        self.assertEqual(out['reply'], 'See [1] and [2].')

    def test_link_chosen_by_number(self):
        out = self.run_reply({'terms': ['manual']}, [{'reply': 'Use the guide [1].', 'used': [1], 'links': [1]}],
                             message='orbit manual')
        self.assertEqual(out['links'], [('https://example.com/setup', 'Setup guide')])

    def test_bad_link_number_ignored(self):
        out = self.run_reply({'terms': ['manual']}, [{'reply': 'Use the guide [1].', 'used': [1], 'links': [9]}],
                             message='orbit manual')
        self.assertEqual(out['links'], [])

    def test_links_offered_from_full_text(self):
        long_case = {'text': 'Orbit manual\n' + 'x ' * 1500 + '\nhttps://example.com/end', 'archive': 'Vault'}
        self.chat.side_effect = [{'terms': ['manual']}, {'reply': 'See it [1].', 'used': [1], 'links': [1]}]
        out = keeper.reply('orbit manual', [], [long_case])
        self.assertIn('L1: https://example.com/end', self.chat.call_args_list[1].args[1])
        self.assertEqual(out['links'], [('https://example.com/end', '')])


NOTE = {'text': 'Total mismatch on panel\n\nScript one checks the fields.\n\n'
                '| Table | Field |\n| --- | --- |\n| Orders | Sum |\n\n'
                'If the gap is one cent, delete the cent line in Orders.\n\n'
                'If there is no cent line, subtract the gap from any line in all tables, '
                'so it must match the report total.\n\n'
                'If the gap is over 1000, fix it by hand.\n\n'
                '---\nPanel Tool\n---\nAccount 44-90 must be open.\n---\nOK\n---\n\n'
                'This error is fixed in table 77, set Gap to 0.00.', 'archive': 'Vault'}
ERROR = '--- Panel Tool --- Panel total 1 280.18 is not equal to report total 1 280.2 --- OK ---'
NAMES = {'names': ['Panel total', 'report total']}
SIDE = {'answer': 'yes'}
STEPS = {'steps': ['Check Orders for cent lines.', 'Add 0.02 to any line in all tables.'],
         'after': ['If «Account 44-90 must be open» appears: set Gap to 0.00 in table 77.']}
PLAN = ('Change «Panel total»: add 0.02 (1 280.18 → 1 280.20, as «report total»). '
        'That is exactly 2 × 0.01.')


class Fix(unittest.TestCase):
    def setUp(self):
        mock.patch.object(keeper, 'active', return_value=CONN).start()
        self.addCleanup(mock.patch.stopall)
        self.calls = []

    def run_fix(self, writes, names=NAMES, side=SIDE, message=ERROR):
        writes = list(writes)

        def chat(system, user, history=None, temperature=0):
            self.calls.append(user)
            if 'Return {"names"' in user:
                return names
            if 'Sentence of the note:' in user:
                return side
            if keeper._LIMIT_TASK in user:
                if 'one cent' in user:
                    return {'op': 'equal', 'words': 'one cent', 'value': 0.01}
                if 'over 1000' in user:
                    return {'op': 'above', 'words': 'over 1000', 'value': 1000}
                return {'op': 'none'}
            return writes.pop(0)

        with mock.patch.object(keeper, '_chat', side_effect=chat):
            return keeper.reply(message, [], CASES, [NOTE], NOTE)

    def writes(self):
        return [user for user in self.calls if keeper._FIX_RULES in user]

    def test_steps_and_calculation(self):
        out = self.run_fix([STEPS])
        self.assertEqual(out['reply'], '1. Check Orders for cent lines.\n2. Add 0.02 to any line in all tables.')
        self.assertEqual(out['after'], STEPS['after'])
        self.assertEqual(out['calc'], {'rows': [('Panel total', '1 280.18'), ('report total', '1 280.20')],
                                       'diff': '0.02', 'target': 1, 'plan': PLAN,
                                       'basis': 'If there is no cent line, subtract the gap from any line in all '
                                                'tables, so it must match the report total.'})
        self.assertEqual((out['archive'], out['online'], out['sources'], out['lookup']), (True, True, [], False))

    def test_write_prompt(self):
        self.run_fix([STEPS])
        user = self.writes()[0]
        self.assertIn(f'Computed by Holocron, exact, trust these:\n{PLAN}', user)
        self.assertIn('delete the cent line in Orders', user)
        self.assertNotIn('fix it by hand', user)
        self.assertIn('Later errors, may appear after the fix:\n---\nPanel Tool', user)
        self.assertIn('This error is fixed in table 77', user)
        self.assertLess(user.index('Note:'), user.index('Later errors'))

    def test_limits_asked_once_per_text_paragraph(self):
        self.run_fix([STEPS])
        asked = [user for user in self.calls if keeper._LIMIT_TASK in user]
        self.assertEqual(len(asked), 5)
        self.assertFalse(any('| Orders | Sum |' in user for user in asked))
        self.assertFalse(any('table 77' in user for user in asked))

    def test_invented_number_retried_with_reason(self):
        bad = {'steps': ['Add 0.02 to line 55.'], 'after': STEPS['after']}
        out = self.run_fix([bad, STEPS])
        self.assertEqual(out['reply'], '1. Check Orders for cent lines.\n2. Add 0.02 to any line in all tables.')
        retry = self.writes()[1]
        self.assertIn('Fix these problems: numbers that are not in the note: 55', retry)
        self.assertIn('"Add 0.02 to line 55."', retry)

    def test_invented_twice_hides_steps(self):
        bad = {'steps': ['Add 0.02 to line 55.'], 'after': STEPS['after']}
        out = self.run_fix([bad, bad])
        self.assertEqual((out['reply'], out['after'], out['archive']), ('', [], False))
        self.assertEqual(out['calc']['plan'], PLAN)
        self.assertEqual(len(self.writes()), 2)

    def test_gaps_retried_but_not_hidden(self):
        thin = {'steps': ['Check Orders for cent lines.'], 'after': []}
        out = self.run_fix([thin, thin])
        self.assertEqual(out['reply'], '1. Check Orders for cent lines.')
        retry = self.writes()[1]
        self.assertIn('say what to do if a later error appears', retry)
        self.assertIn('mention the difference 0.02', retry)

    def test_total_and_label_flagged(self):
        bad = {'steps': ['Set Panel total to 1 280.2.'], 'after': STEPS['after']}
        self.run_fix([bad, STEPS])
        retry = self.writes()[1]
        self.assertIn('do not write the totals anywhere', retry)
        self.assertIn('the names from the error message are not field names', retry)

    def test_unknown_side(self):
        out = self.run_fix([STEPS], side={'answer': 'no'})
        self.assertEqual(out['calc']['target'], None)
        self.assertEqual(out['calc']['basis'], '')
        self.assertEqual(out['calc']['plan'],
                         '«Panel total» is 0.02 less than «report total». Which one is correct is unknown: '
                         'either add 0.02 to «Panel total» or subtract 0.02 from «report total». '
                         'That is exactly 2 × 0.01.')

    def test_only_sentences_naming_a_value_asked(self):
        self.run_fix([STEPS])
        asked = [user for user in self.calls if 'Sentence of the note:' in user]
        self.assertEqual(len(asked), 1)
        self.assertIn('so it must match the report total.', asked[0])
        self.assertIn('«report total»', asked[0])
        self.assertNotIn('Total mismatch on panel', asked[0])

    def test_unknown_side_is_neutral_for_writer(self):
        self.run_fix([STEPS], side={'answer': 'no'})
        user = self.writes()[0]
        self.assertIn('The difference is 0.02. That is exactly 2 × 0.01. Which value is correct is not computed', user)
        self.assertNotIn('either add', user)

    def test_after_without_later_error_dropped(self):
        vague = {'steps': STEPS['steps'], 'after': ['If «error» appears: check again.']}
        out = self.run_fix([vague, vague])
        self.assertEqual(out['after'], [])
        self.assertIn('each item of "after"', self.writes()[1])

    def test_names_not_in_message_fall_back(self):
        out = self.run_fix([STEPS], names={'names': ['Invented name', 'report total']})
        self.assertEqual([label for label, _ in out['calc']['rows']],
                         ['Panel total', 'is not equal to report total'])

    def test_garbage_from_model(self):
        out = self.run_fix([{'steps': 'x'}, {}], names={'names': 'x'}, side={'answer': None})
        self.assertEqual(out['reply'], '')
        self.assertIsNone(out['calc']['target'])

    def test_error_window_without_amounts(self):
        out = self.run_fix([{'steps': ['Set Gap to 0.00 in table 77.']}],
                           message='--- Panel Tool --- Account 44-90 must be open --- OK ---')
        self.assertEqual(out['reply'], '1. Set Gap to 0.00 in table 77.')
        self.assertIsNone(out['calc'])
        self.assertEqual(len(self.calls), 1)

    def test_offline_falls_back_to_words(self):
        with mock.patch.object(keeper, '_chat', side_effect=keeper.KeeperOffline('down')):
            out = keeper.reply(ERROR, [], CASES, [NOTE], NOTE)
        self.assertFalse(out['online'])
        self.assertEqual(out['reply'], '')


class Explain(unittest.TestCase):
    def setUp(self):
        mock.patch.object(keeper, 'active', return_value=CONN).start()
        self.chat = mock.patch.object(keeper, '_chat').start()
        self.addCleanup(mock.patch.stopall)

    def ask(self, answers, message='what to do'):
        self.chat.side_effect = answers
        return keeper.reply(message, [], CASES, [NOTE], NOTE)

    def test_reads_only_open_record(self):
        out = self.ask([{'reply': 'Delete the cent line.', 'quotes': ['delete the cent line in Orders']}])
        self.assertEqual(self.chat.call_count, 1)
        prompt, user = self.chat.call_args.args[:2]
        self.assertIs(prompt, keeper._FOCUS_PROMPT)
        self.assertTrue(user.startswith('Record: Total mismatch on panel\n\n'))
        self.assertTrue(user.endswith('\n\nMessage: what to do'))
        self.assertNotIn('Orbit manual', user)
        self.assertEqual((out['reply'], out['sources'], out['missing']), ('Delete the cent line.', [], False))
        self.assertEqual(out['calc'], None)

    def test_steady_first_then_retry(self):
        out = self.ask([{'reply': 'Use table 99.'}, {'reply': 'Use table 77.'}])
        self.assertEqual(out['reply'], 'Use table 77.')
        self.assertEqual([c.args[3] for c in self.chat.call_args_list], [0, keeper.CHAT_TEMPERATURE])

    def test_not_in_record(self):
        out = self.ask([{'reply': 'Not in this record.', 'found': False}])
        self.assertEqual((out['missing'], out['archive']), (True, False))


class Values(unittest.TestCase):
    def test_compare(self):
        cmp = keeper._compare(ERROR)
        self.assertEqual(cmp['labels'], ['Panel total', 'is not equal to report total'])
        self.assertEqual(cmp['values'], [Decimal('1280.18'), Decimal('1280.2')])
        self.assertEqual((cmp['diff'], cmp['scale']), (Decimal('0.02'), 2))

    def test_cyrillic_and_comma(self):
        cmp = keeper._compare('Итог 1 280,18 не равен 1 280,2')
        self.assertEqual(cmp['labels'], ['Итог', 'не равен'])
        self.assertEqual(cmp['diff'], Decimal('0.02'))

    def test_no_comparison(self):
        for text in ('', 'nothing here', 'only 1.5', '1.5, 2.5 and 3.5', '5.50 vs 5.5', 'code 99001488 at 12:30'):
            with self.subTest(text=text):
                self.assertIsNone(keeper._compare(text))

    def test_label_fallback(self):
        self.assertEqual(keeper._compare('1.5 2.5')['labels'], ['value 1', 'value 2'])

    def test_units(self):
        self.assertEqual(keeper._units(keeper._compare('a 1.10 b 1.13')), (3, Decimal('0.01')))
        self.assertIsNone(keeper._units(keeper._compare('a 1.10 b 1.25')))
        self.assertIsNone(keeper._units(keeper._compare('a 1 000 b 1 002')))

    def test_limit(self):
        para = 'If the gap is over 1000, fix it by hand.'
        self.assertEqual(keeper._limit({'op': 'above', 'words': 'over 1000', 'value': 1000}, para),
                         ('above', Decimal('1000')))
        self.assertEqual(keeper._limit({'op': 'equal', 'words': 'the gap', 'value': '0,5'}, para),
                         ('equal', Decimal('0.5')))

    def test_limit_rejected(self):
        para = 'If the gap is over 1000, fix it by hand.'
        for data in ({'op': 'none'}, {'op': 'above', 'words': 'over 500', 'value': 500},
                     {'op': 'above', 'words': 'over 1000', 'value': 10}, {'op': 'above', 'words': 'over 1000'},
                     {'op': 'above', 'words': 'over 1000', 'value': 'big'}, {'op': 'above', 'words': '', 'value': 1},
                     {'op': 'above', 'words': 'the gap', 'value': -1}, {'op': 'more', 'words': 'over 1000', 'value': 1000},
                     {'op': 'above', 'words': 'the gap', 'value': 'NaN'}):
            with self.subTest(data=data):
                self.assertIsNone(keeper._limit(data, para))

    def test_split_later_needs_frame(self):
        paras = keeper._paragraphs(NOTE['text'])
        self.assertEqual(keeper._split_later(paras, 'what to do'), (paras, []))
        main, later = keeper._split_later(paras, ERROR)
        self.assertTrue(later[0].startswith('---\nPanel Tool'))
        self.assertEqual(main + later, paras)

    def test_same_error_is_not_later(self):
        paras = keeper._paragraphs(NOTE['text'])
        self.assertEqual(keeper._split_later(paras, '--- Panel Tool --- Account 44-90 must be open ---'), (paras, []))




class Language(unittest.TestCase):
    NOTE = 'Список Альфа'
    FAULT = 'write in the language of the note'

    def faults(self, steps, note=NOTE, after=()):
        return keeper._faults(steps, list(after), note, note)

    def test_new_latin_words_in_cyrillic_note(self):
        self.assertEqual(self.faults(['Check Список Альфа']), [self.FAULT])

    def test_only_words_of_note(self):
        self.assertEqual(self.faults(['Список Альфа']), [])

    def test_new_words_in_same_script(self):
        self.assertEqual(self.faults(['Бета Список Альфа']), [])

    def test_latin_names_from_cyrillic_note(self):
        self.assertEqual(self.faults(['Бета Alpha'], 'Список Альфа Alpha'), [])

    def test_latin_note(self):
        self.assertEqual(self.faults(['Open Alpha'], 'Close Alpha'), [])
        self.assertEqual(self.faults(['Альфа Alpha'], 'Close Alpha'), [self.FAULT])

    def test_after_counts(self):
        self.assertEqual(self.faults(['Список Альфа'], after=['Then check']), [self.FAULT])

    def test_empty_steps(self):
        self.assertEqual(self.faults([]), ['the steps are empty'])


class Paragraphs(unittest.TestCase):
    def test_blank_lines(self):
        self.assertEqual(keeper._paragraphs('a\n\n\n b \nc\n \n'), ['a', 'b\nc'])

    def test_windows_line_ends(self):
        self.assertEqual(keeper._paragraphs('a\r\n\r\nb\r\nc'), ['a', 'b\nc'])

    def test_cyrillic(self):
        self.assertEqual(keeper._paragraphs('Шаг один\n\nШаг два'), ['Шаг один', 'Шаг два'])

    def test_empty(self):
        for text in ('', '\n\n', '   '):
            with self.subTest(text=text):
                self.assertEqual(keeper._paragraphs(text), [])

    def test_count_capped(self):
        with mock.patch.object(keeper, 'MAX_PARAGRAPHS', 2):
            self.assertEqual(keeper._paragraphs('a\n\nb\n\nc'), ['a', 'b'])

    def test_size_capped(self):
        with mock.patch.object(keeper, 'FOCUS', 5):
            self.assertEqual(keeper._paragraphs('abcd\n\nefgh\n\nij'), ['abcd', 'e'])


class Think(unittest.TestCase):
    def test_always_off(self):
        with mock.patch.object(keeper, '_get_json', return_value={'message': {'content': '{"quotes": []}'}}) as get:
            self.assertEqual(keeper._chat_with(CONN, 's', 'u', None, 0), {'quotes': []})
        self.assertIs(get.call_args.args[2]['think'], False)

    def test_http_errors_are_offline(self):
        for code in (400, 500):
            error = urllib.error.HTTPError('http://x', code, 'bad', None, None)
            self.addCleanup(error.close)
            with self.subTest(code=code), mock.patch.object(keeper, '_get_json', side_effect=error) as get:
                with self.assertRaises(keeper.KeeperOffline):
                    keeper._chat_with(CONN, 's', 'u', None, 0)
                self.assertEqual(get.call_count, 1)


class Offline(unittest.TestCase):
    def test_calculation_dropped_when_model_goes_offline(self):
        def weigh(cmp, main, message, focus, out):
            out['calc'] = {'rows': []}
            return '', main

        focus = {'text': 'Alpha step one\n\nBeta step two', 'filename': 'note'}
        with mock.patch.object(keeper, 'active', return_value={'slot': 'local'}), \
             mock.patch.object(keeper, '_weigh', side_effect=weigh), \
             mock.patch.object(keeper, '_write', side_effect=keeper.KeeperOffline('down')), \
             mock.patch.object(keeper, '_candidates', return_value=[]):
            out = keeper.reply('Total 1 000.10 is not equal to 1 000.30', [], [focus], [focus], focus)
        self.assertFalse(out['online'])
        self.assertIsNone(out['calc'])
        self.assertEqual(out['reply'], '')
        self.assertTrue(out['lookup'])


class History(unittest.TestCase):
    def test_turns_to_messages(self):
        turns = [{'question': 'relay?', 'reply': 'Fuse.', 'sources': [RELAY], 'start': 1},
                 {'question': 'x', 'reply': '', 'sources': [], 'start': 2}]
        msgs = keeper.history(turns)
        self.assertEqual([m['role'] for m in msgs], ['user', 'assistant'])
        self.assertIn('[1] Relay fault on orbit sensor', json.loads(msgs[1]['content'])['reply'])

    def test_links_kept(self):
        turns = [{'question': 'guide?', 'reply': 'Here.', 'sources': [], 'start': 1,
                  'links': [('https://example.com/setup', 'Setup guide')]}]
        self.assertIn('Link given: https://example.com/setup', json.loads(keeper.history(turns)[1]['content'])['reply'])


if __name__ == '__main__':
    unittest.main()
