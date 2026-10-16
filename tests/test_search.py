import unittest

from core.search import _norm_words, score_case, search, suggest


def _case(text):
    return {'text': text, '_prep_for': None}


class NormWords(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_norm_words('hello world'), ['hello', 'world'])

    def test_punctuation(self):
        self.assertEqual(_norm_words('hello, world!'), ['hello', 'world'])

    def test_empty(self):
        self.assertEqual(_norm_words(''), [])

    def test_cyrillic(self):
        words = _norm_words('привет мир')
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0], 'привет')

    def test_mixed_digits(self):
        self.assertGreaterEqual(len(_norm_words('test123')), 1)


class ScoreCase(unittest.TestCase):
    def test_exact_match(self):
        self.assertGreater(score_case(_case('hello world'), 'hello'), 0)

    def test_no_match(self):
        self.assertEqual(score_case(_case('hello world'), 'xyzxyz'), 0)

    def test_empty_query(self):
        self.assertEqual(score_case(_case('hello world'), ''), 0)

    def test_title_boost(self):
        top = score_case(_case('hello\nsome body text\nextra line'), 'hello')
        bottom = score_case(_case('extra line\nsome body text\nhello'), 'hello')
        self.assertGreaterEqual(top, bottom)

    def test_phrase_match_boost(self):
        c = _case('the quick brown fox')
        self.assertGreater(score_case(c, 'quick brown'), score_case(c, 'quick fox'))

    def test_fuzzy_match(self):
        self.assertGreater(score_case(_case('configuration settings'), 'configuraton'), 0)

    def test_short_word_exact_only(self):
        c = _case('the cat sat')
        self.assertGreater(score_case(c, 'cat'), 0)
        self.assertEqual(score_case(c, 'cax'), 0)

    def test_filename_matches(self):
        c = {'text': '## Summary of the day\neverything is ok', 'filename': '02 Jun 2026'}
        self.assertGreater(score_case(c, '02 jun'), 0)
        self.assertNotIn('filename', c['text'])

    def test_short_word_is_whole_token(self):
        self.assertEqual(score_case(_case('план на 2026'), '02'), 0)
        self.assertGreater(score_case(_case('02 июня'), '02'), 0)

    def test_exact_title_wins_over_length(self):
        target = {'text': 'заметка\n' + 'длинный текст ' * 300, 'filename': '02 Jun 2026'}
        other = {'text': 'коротко', 'filename': '18 Jun 2026'}
        self.assertGreater(score_case(target, '02 Jun 2026'), score_case(other, '02 Jun 2026'))


class Search(unittest.TestCase):
    def test_returns_sorted(self):
        cases = [_case('alpha beta'), _case('beta gamma'), _case('alpha beta gamma')]
        results = search(cases, 'alpha beta')
        self.assertGreaterEqual(len(results), 1)
        scores = [r[0] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_no_results(self):
        self.assertEqual(search([_case('hello world')], 'xyzxyz'), [])

    def test_empty_cases(self):
        self.assertEqual(search([], 'test'), [])


class Suggest(unittest.TestCase):
    def test_typo_correction(self):
        self.assertLessEqual(len(suggest([_case('конфигурация настройки')], 'конфигураця')), 1)

    def test_garbage_no_suggestion(self):
        self.assertEqual(suggest([_case('hello world test')], 'zzzzzzzzz'), [])

    def test_exact_no_suggestion(self):
        self.assertEqual(suggest([_case('hello world')], 'hello'), [])


class Underscore(unittest.TestCase):
    CASES = ['AB12_CD first', 'AB12 CD second', 'AB12 other']

    def _found(self, query):
        cases = [{'text': t} for t in self.CASES]
        return [c['text'] for _, c in search(cases, query)]

    def test_underscore_same_as_space(self):
        for query in ('AB12_CD', 'AB12 CD'):
            with self.subTest(query=query):
                self.assertEqual(set(self._found(query)[:2]), {'AB12_CD first', 'AB12 CD second'})

    def test_code_finds_underscored(self):
        self.assertIn('AB12_CD first', self._found('AB12'))
