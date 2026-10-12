import unittest

from core import wikilinks


def _note(path):
    return {'filepath': path, 'filename': path.rsplit('/', 1)[-1][:-3], 'text': 'x'}


CASES = [
    _note('/v/Hardware.md'),
    _note('/v/Work/Setup.md'),
    _note('/v/Old/Deep/Setup.md'),
    {'filepath': '/v/Plan.excalidraw.md', 'element_id': 'a', 'text': 'one'},
    {'filepath': '/v/Plan.excalidraw.md', 'element_id': 'b', 'text': 'two'},
]


def _mark(shown, n):
    return f'{shown}<{n}>'


def _run(text):
    return wikilinks.numbered(text, CASES, _mark)


class Numbered(unittest.TestCase):
    def test_note_and_alias_share_number(self):
        text, found = _run('See [[Hardware]] and [[hardware|the box]]')
        self.assertEqual(text, 'See Hardware<1> and the box<1>')
        self.assertEqual(len(found), 1)

    def test_missing_plain(self):
        text, found = _run('[[Nowhere]] here')
        self.assertEqual((text, found), ('Nowhere here', []))

    def test_board_all_blocks(self):
        text, found = _run('[[Plan]]')
        self.assertEqual(text, 'Plan<1>')
        self.assertEqual([c['text'] for c in found[0]], ['one', 'two'])

    def test_heading(self):
        text, _ = _run('[[Hardware#Fans]]')
        self.assertEqual(text, 'Hardware › Fans<1>')

    def test_shallowest_wins(self):
        _, found = _run('[[Setup]]')
        self.assertEqual(found[0][0]['filepath'], '/v/Work/Setup.md')

    def test_path(self):
        _, found = _run('[[Old/Deep/Setup]]')
        self.assertEqual(found[0][0]['filepath'], '/v/Old/Deep/Setup.md')

    def test_suffix(self):
        _, found = _run('[[Hardware.md]]')
        self.assertEqual(len(found), 1)

    def test_url_and_embed_untouched(self):
        raw = '[[https://example.com|site]] ![[image.png]]'
        self.assertEqual(_run(raw), (raw, []))

    def test_order(self):
        text, found = _run('[[Plan]] then [[Hardware]]')
        self.assertEqual(text, 'Plan<1> then Hardware<2>')
        self.assertEqual(found[1][0]['filepath'], '/v/Hardware.md')

    def test_self_anchor_plain(self):
        self.assertEqual(_run('[[#Top]]'), ('Top', []))


if __name__ == '__main__':
    unittest.main()
