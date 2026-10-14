import difflib
import unittest

from core import search


class Similarity(unittest.TestCase):
    def test_matches_difflib(self):
        for a, b in (('server', 'servre'), ('kafka', 'zookeeper'), ('nginx', 'nginz')):
            self.assertEqual(search.similarity(a, b), difflib.SequenceMatcher(None, a, b).ratio())

    def test_prefix_floor(self):
        self.assertGreaterEqual(search.similarity('deploy', 'deployment'), 0.85)


class Stable(unittest.TestCase):
    CASES = ('Restart the nginx server', 'Kafka consumer lag', 'Server disk full')

    def run_query(self, query):
        cases = [{'text': t} for t in self.CASES]
        return [(s, c['text']) for s, c in search.search(cases, query)]

    def test_repeat_same(self):
        first = self.run_query('servr restart')
        self.assertTrue(first)
        self.assertEqual(self.run_query('servr restart'), first)

    def test_text_change_reprepped(self):
        case = {'text': 'alpha beta'}
        self.assertTrue(search.search([case], 'alpha'))
        case['text'] = 'gamma delta'
        self.assertFalse(search.search([case], 'alpha'))

    def test_title_bonus_kept(self):
        title = {'text': 'nginx\nsomething else\nmore'}
        body = {'text': 'something else\nmore\nnginx'}
        ranked = [c['text'] for _, c in search.search([body, title], 'nginx')]
        self.assertEqual(ranked[0], title['text'])
