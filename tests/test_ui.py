import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screens.search_screen import highlight, highlight_links, first_line
from ui.clean_path import clean_input_path


class TestHighlight:
    def test_highlights_match(self):
        result = highlight('hello world', 'hello')
        assert '\033[' in result
        assert 'hello' in result

    def test_no_match_unchanged(self):
        result = highlight('hello world', 'xyz')
        assert result == 'hello world'

    def test_empty_query(self):
        result = highlight('hello world', '')
        assert result == 'hello world'

    def test_cyrillic(self):
        result = highlight('привет мир', 'привет')
        assert '\033[' in result


class TestHighlightLinks:
    def test_dims_url(self):
        result = highlight_links('see https://example.com here')
        assert '\033[2m' in result
        assert 'https://example.com' in result

    def test_no_url(self):
        result = highlight_links('no links here')
        assert result == 'no links here'


class TestFirstLine:
    def test_normal(self):
        assert first_line({'text': 'hello\nworld'}) == 'hello'

    def test_empty_first_line(self):
        assert first_line({'text': '\nhello'}) == 'hello'

    def test_empty_text(self):
        assert first_line({'text': ''}) == '(empty)'

    def test_whitespace_only(self):
        assert first_line({'text': '   \n   '}) == '(empty)'


class TestCleanPath:
    def test_basic(self):
        result = clean_input_path('/Users/test/file.md')
        assert result == '/Users/test/file.md'

    def test_strips_quotes(self):
        result = clean_input_path('"~/file.md"')
        assert '~' not in result or '/Users' in result

    def test_empty(self):
        assert clean_input_path('') == ''

    def test_tilde(self):
        result = clean_input_path('~/test')
        assert '~' not in result
