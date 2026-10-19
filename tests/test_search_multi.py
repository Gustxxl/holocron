import unittest

from core import search


def _case(text):
    return {'text': text}


class Split(unittest.TestCase):
    def test_parts(self):
        self.assertEqual(search.split('nginx; timeout', ';'), ['nginx', 'timeout'])

    def test_empty_and_repeated(self):
        self.assertEqual(search.split(' timeout ;; Timeout; ', ';'), ['timeout'])

    def test_off(self):
        self.assertEqual(search.split('a;b', ''), ['a;b'])


class Many(unittest.TestCase):
    def test_each_query_gets_its_group(self):
        cases = [_case('nginx timeout'), _case('disk full')]
        groups, missing = search.search_many(cases, ['nginx', 'disk'])
        self.assertEqual([[c['text'] for _, c in g] for g in groups], [['nginx timeout'], ['disk full']])
        self.assertEqual(missing, [])

    def test_shared_case_shown_once(self):
        groups, _ = search.search_many([_case('nginx timeout')], ['nginx', 'timeout'])
        self.assertEqual(sum(len(g) for g in groups), 1)

    def test_missing_query(self):
        _, missing = search.search_many([_case('nginx timeout')], ['nginx', 'kafka'])
        self.assertEqual(missing, ['kafka'])


if __name__ == '__main__':
    unittest.main()
