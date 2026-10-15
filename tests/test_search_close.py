import unittest

from core import search

FRAME = 'Acme Console\n---\n{}\n---\nOK'
NOISE = [{'text': FRAME.format(f'Batch {n} could not be posted')} for n in range(30)]
FILLER = [{'text': f'Routine note {n}'} for n in range(10)]
FULL = {'text': 'Orbit sensor relay fault: no signal'}
PARTIAL = {'text': 'Sensor offline, relay fault'}


def _found(cases, query):
    return [c['text'] for _, c in search.search(cases, query)]


class Words(unittest.TestCase):
    def test_forms(self):
        for a, b in (('delete', 'deleting'), ('allocation', 'allocations'), ('restarting', 'restarted'),
                     ('rotation', 'rotated'), ('configure', 'configuration')):
            self.assertGreater(search.word_match(a, b), 0, (a, b))

    def test_typos(self):
        for a, b in (('permision', 'permission'), ('recieve', 'receive'), ('sensro', 'sensor')):
            self.assertGreater(search.word_match(a, b), 0, (a, b))

    def test_shared_ending_not_match(self):
        for a, b in (('allocation', 'location'), ('rejected', 'selected'), ('distribution', 'attribution')):
            self.assertEqual(search.word_match(a, b), 0, (a, b))

    def test_short_word_not_extended(self):
        self.assertEqual(search.word_match('test', 'testament'), 0)

    def test_codes_exact(self):
        self.assertEqual(search.word_match('err4021', 'err4022'), 0)
        self.assertEqual(search.word_match('abx', 'abz'), 0)

    def test_abbreviation(self):
        for a, b in (('distrib', 'distribution'), ('config', 'configuration'), ('allocat', 'allocations')):
            self.assertGreater(search.word_match(a, b), 0, (a, b))

    def test_abbreviation_one_way(self):
        self.assertEqual(search.word_match('distribution', 'distrib'), 0)


class Relevance(unittest.TestCase):
    def test_one_word_is_not_enough(self):
        cases = [{'text': 'Deleting allocations'}, {'text': 'Keyboard shortcuts: delete line, location bar'}]
        self.assertEqual(_found(cases, 'delete allocation'), ['Deleting allocations'])

    def test_frame_alone_finds_nothing(self):
        query = FRAME.format('Item 77031 will be loaded during revaluation')
        self.assertEqual(_found(NOISE, query), [])

    def test_frame_with_code_finds_it(self):
        text = FRAME.format('Item 77031 will be loaded during revaluation')
        results = search.search(NOISE + [{'text': text}], text)
        self.assertEqual([c['text'] for _, c in results], [text])
        self.assertTrue(search.is_exact(results[0][0]))

    def test_skipped_word_still_found(self):
        results = search.search(FILLER + [FULL], 'orbit sensor relay glitch')
        self.assertEqual([c for _, c in results], [FULL])
        self.assertFalse(search.is_exact(results[0][0]))

    def test_exact_first(self):
        results = search.search(FILLER + [PARTIAL, FULL], 'orbit sensor relay fault')
        self.assertEqual([c for _, c in results], [FULL, PARTIAL])
        self.assertTrue(search.is_exact(results[0][0]))
        self.assertFalse(search.is_exact(results[1][0]))

    def test_inflected_query_exact(self):
        results = search.search(FILLER + [{'text': 'Deleting allocations'}], 'delete allocation')
        self.assertTrue(search.is_exact(results[0][0]))

    def test_abbreviated_query(self):
        cases = FILLER + [{'text': 'Deleting distributions'}, {'text': 'Delete line shortcut'}]
        results = search.search(cases, 'delete distrib')
        self.assertEqual([c['text'] for _, c in results], ['Deleting distributions'])
        self.assertTrue(search.is_exact(results[0][0]))


if __name__ == '__main__':
    unittest.main()
