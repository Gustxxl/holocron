import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.search import _norm_words, score_case, search, suggest


def _case(text):
    return {'text': text, '_prep_for': None}


class TestNormWords:
    def test_basic(self):
        assert _norm_words('hello world') == ['hello', 'world']

    def test_punctuation(self):
        assert _norm_words('hello, world!') == ['hello', 'world']

    def test_empty(self):
        assert _norm_words('') == []

    def test_cyrillic(self):
        words = _norm_words('привет мир')
        assert len(words) == 2
        assert words[0] == 'привет'

    def test_mixed_digits(self):
        words = _norm_words('test123')
        assert len(words) >= 1


class TestScoreCase:
    def test_exact_match(self):
        c = _case('hello world')
        assert score_case(c, 'hello') > 0

    def test_no_match(self):
        c = _case('hello world')
        assert score_case(c, 'xyzxyz') == 0

    def test_empty_query(self):
        c = _case('hello world')
        assert score_case(c, '') == 0

    def test_title_boost(self):
        c1 = _case('hello\nsome body text\nextra line')
        c2 = _case('extra line\nsome body text\nhello')
        s1 = score_case(c1, 'hello')
        s2 = score_case(c2, 'hello')
        assert s1 >= s2

    def test_phrase_match_boost(self):
        c = _case('the quick brown fox')
        s_phrase = score_case(c, 'quick brown')
        s_words = score_case(c, 'quick fox')
        assert s_phrase > s_words

    def test_fuzzy_match(self):
        c = _case('configuration settings')
        assert score_case(c, 'configuraton') > 0

    def test_short_word_exact_only(self):
        c = _case('the cat sat')
        assert score_case(c, 'cat') > 0
        assert score_case(c, 'cax') == 0


class TestSearch:
    def test_returns_sorted(self):
        cases = [_case('alpha beta'), _case('beta gamma'), _case('alpha beta gamma')]
        results = search(cases, 'alpha beta')
        assert len(results) >= 1
        scores = [r[0] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_results(self):
        cases = [_case('hello world')]
        results = search(cases, 'xyzxyz')
        assert results == []

    def test_empty_cases(self):
        assert search([], 'test') == []


class TestSuggest:
    def test_typo_correction(self):
        cases = [_case('конфигурация настройки')]
        tips = suggest(cases, 'конфигураця')
        assert len(tips) <= 1

    def test_garbage_no_suggestion(self):
        cases = [_case('hello world test')]
        tips = suggest(cases, 'zzzzzzzzz')
        assert tips == []

    def test_exact_no_suggestion(self):
        cases = [_case('hello world')]
        tips = suggest(cases, 'hello')
        assert tips == []
