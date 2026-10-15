import json
import unittest
from unittest import mock

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

    def test_focus_always_read_not_listed(self):
        out = self.run_reply({'terms': []}, [{'reply': 'It covers a relay fault [1].', 'used': [1]}],
                             message='summarize this', records=[RELAY], focus=RELAY)
        self.assertIn('Check the harness', self.chat.call_args_list[1].args[1])
        self.assertTrue(out['archive'])
        self.assertEqual(out['sources'], [])

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


class Offline(unittest.TestCase):
    def test_words_only(self):
        with mock.patch.object(keeper, 'active', return_value=None), \
             mock.patch.object(keeper, '_chat') as chat:
            out = keeper.reply('relay fault', [], CASES)
        chat.assert_not_called()
        self.assertFalse(out['online'])
        self.assertIn(RELAY, out['sources'])


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
