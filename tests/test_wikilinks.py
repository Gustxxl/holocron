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

    def test_missing_search(self):
        text, found = _run('[[Nowhere]] here')
        self.assertEqual((text, found), ('Nowhere<1> here', ['Nowhere']))

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


MAP = '/v/Map.excalidraw.md'
OTHER = '/v/Other.excalidraw.md'


def _block(path, eid, text):
    return {'filepath': path, 'element_id': eid, 'text': text}


BOARDS = [
    _block(MAP, 'm1', 'First Block\nbody'),
    _block(MAP, 'm2', 'Ёлка'),
    _block(MAP, 'm3', 'Shared'),
    _block(MAP, 'm4', 'Twin'),
    _block(MAP, 'm5', 'Twin'),
    _block(MAP, 'm6', 'Setup'),
    _block(OTHER, 'o1', 'Shared'),
    _block(OTHER, 'o2', 'Hardware'),
    _block(OTHER, 'o3', 'Only here'),
]


def _at(text, here=None):
    return wikilinks.numbered(text, CASES + BOARDS, _mark, here=here)


def _ids(hit):
    return [c['element_id'] for c in hit]


class Blocks(unittest.TestCase):
    def test_own_board_title(self):
        text, found = _at('[[First Block]]', MAP)
        self.assertEqual(text, 'First Block<1>')
        self.assertEqual(_ids(found[0]), ['m1'])

    def test_title_loose(self):
        _, found = _at('[[  first   BLOCK ]]', MAP)
        self.assertEqual(_ids(found[0]), ['m1'])

    def test_title_yo(self):
        _, found = _at('[[елка]]', MAP)
        self.assertEqual(_ids(found[0]), ['m2'])

    def test_own_board_first(self):
        _, found = _at('[[Shared]]', MAP)
        self.assertEqual(_ids(found[0]), ['m3'])

    def test_own_board_beats_note(self):
        _, found = _at('[[Setup]]', MAP)
        self.assertEqual(_ids(found[0]), ['m6'])

    def test_note_beats_other_board(self):
        _, found = _at('[[Hardware]]', MAP)
        self.assertEqual(found[0][0]['filepath'], '/v/Hardware.md')

    def test_other_board_title(self):
        _, found = _at('[[Only here]]', MAP)
        self.assertEqual(_ids(found[0]), ['o3'])

    def test_from_note(self):
        _, found = _at('[[Only here]]', '/v/Hardware.md')
        self.assertEqual(_ids(found[0]), ['o3'])

    def test_twins_search(self):
        self.assertEqual(_at('[[Twin]]', MAP), ('Twin<1>', ['Twin']))

    def test_ambiguous_from_note_search(self):
        self.assertEqual(_at('[[Shared]]', '/v/Hardware.md'), ('Shared<1>', ['Shared']))

    def test_board_anchor(self):
        text, found = _at('[[Other#Only here]]')
        self.assertEqual(text, 'Other › Only here<1>')
        self.assertEqual(_ids(found[0]), ['o3'])

    def test_board_anchor_missing(self):
        _, found = _at('[[Other#Nothing]]')
        self.assertEqual(_ids(found[0]), ['o1', 'o2', 'o3'])

    def test_missing_shares_number(self):
        text, found = _at('[[Nowhere]] and [[nowhere|again]]', MAP)
        self.assertEqual(text, 'Nowhere<1> and again<1>')
        self.assertEqual(found, ['Nowhere'])

    def test_block_and_board_apart(self):
        text, found = _at('[[First Block]] [[Map]] [[first block]]', MAP)
        self.assertEqual(text, 'First Block<1> Map<2> first block<1>')
        self.assertEqual(len(found), 2)

    def test_self_anchor_block(self):
        _, found = _at('[[#First Block]]', MAP)
        self.assertEqual(_ids(found[0]), ['m1'])

    def test_self_anchor_missing_search(self):
        self.assertEqual(_at('[[#Nothing]]', MAP), ('Nothing<1>', ['Nothing']))

    def test_self_anchor_twins_search(self):
        self.assertEqual(_at('[[#Twin]]', MAP), ('Twin<1>', ['Twin']))

    def test_self_anchor_note_plain(self):
        self.assertEqual(_at('[[#First Block]]', '/v/Hardware.md'), ('First Block', []))


if __name__ == '__main__':
    unittest.main()
