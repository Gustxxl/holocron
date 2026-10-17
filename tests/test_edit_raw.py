import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from core import excalidraw

from core.archives import excalidraw_plain
from core.excalidraw import load_cases
from screens import search_screen
from core import backups


def setUpModule():
    tmp = tempfile.TemporaryDirectory()
    patch = mock.patch.object(backups, 'DIR', Path(tmp.name))
    patch.start()
    unittest.addModuleCleanup(patch.stop)
    unittest.addModuleCleanup(tmp.cleanup)

BACKUPS = Path(__file__).resolve().parent.parent / 'data' / 'backups'
TEXT = '🔥 Prod down'
SCENE = {'type': 'excalidraw', 'elements': [
    {'id': 'a1', 'type': 'text', 'x': 0, 'y': 0, 'text': TEXT, 'originalText': TEXT},
]}
DRAWING = '---\nexcalidraw-plugin: parsed\n---\n\n## Drawing\n```json\n' + json.dumps(SCENE, ensure_ascii=False) + '\n```\n'
BOARD = {'type': 'excalidraw', 'elements': [
    {'id': 'a1', 'type': 'text', 'x': 0, 'y': 0, 'text': TEXT, 'originalText': TEXT},
    {'id': 'b2', 'type': 'text', 'x': 0, 'y': 100, 'text': '🚀 Deploy', 'originalText': '🚀 Deploy'},
]}
COMPRESSED = ('---\nexcalidraw-plugin: parsed\n---\n\n## Text Elements\n'
              f'{TEXT} ^a1\n\n🚀 Deploy ^b2\n\n%%\n## Drawing\n```compressed-json\n'
              + excalidraw.compress_to_base64(json.dumps(BOARD, ensure_ascii=False)) + '\n```\n%%\n')


def _temp(test, suffix, text):
    fd, name = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    path = Path(name)
    test.addCleanup(path.unlink, missing_ok=True)
    test.addCleanup((BACKUPS / path.name).unlink, missing_ok=True)
    return path


class Raw(unittest.TestCase):
    def test_obsidian_keeps_raw(self):
        case = load_cases(_temp(self, '.md', DRAWING))[0]
        self.assertEqual((case['text'], case['raw']), ('Prod down', TEXT))

    def test_plain_keeps_raw(self):
        case = excalidraw_plain._load_scene(_temp(self, '.excalidraw', json.dumps(SCENE, ensure_ascii=False)))[0]
        self.assertEqual((case['text'], case['raw']), ('Prod down', TEXT))


class Edit(unittest.TestCase):
    def edit(self, path, change):
        case = load_cases(path)[0]
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen, 'read_command', side_effect=['e', 'b']), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen, 'haptic'), \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', side_effect=change) as edit:
            search_screen.open_case([(0, case)], 1, '')
        return case, edit

    def test_editor_gets_raw_text(self):
        _, edit = self.edit(_temp(self, '.md', DRAWING), lambda t: t.replace('down', 'up'))
        edit.assert_called_once_with(TEXT)

    def test_emoji_kept_on_board(self):
        path = _temp(self, '.md', DRAWING)
        self.edit(path, lambda t: t.replace('down', 'up'))
        self.assertEqual(load_cases(path)[0]['raw'], '🔥 Prod up')

    def test_case_updated_after_save(self):
        case, _ = self.edit(_temp(self, '.md', DRAWING), lambda t: t.replace('down', 'up'))
        self.assertEqual((case['text'], case['raw']), ('Prod up', '🔥 Prod up'))

    def test_unchanged_text_not_saved(self):
        path = _temp(self, '.md', DRAWING)
        before = path.read_text(encoding='utf-8')
        self.edit(path, lambda t: t)
        self.assertEqual(path.read_text(encoding='utf-8'), before)


class Compressed(unittest.TestCase):
    def test_utf16_pairs(self):
        self.assertEqual(excalidraw._to_utf16('🔥a'), '\ud83d\udd25a')
        self.assertEqual(excalidraw._from_utf16('\ud83d\udd25a'), '🔥a')

    def test_roundtrip(self):
        s = json.dumps(BOARD, ensure_ascii=False)
        self.assertEqual(excalidraw.decompress_from_base64(excalidraw.compress_to_base64(s)), s)

    def test_loads_emoji(self):
        cases = load_cases(_temp(self, '.md', COMPRESSED))
        self.assertEqual([c['raw'] for c in cases], [TEXT, '🚀 Deploy'])

    def test_edit_keeps_other_blocks(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'a1', '🔥 Prod up')
        self.assertEqual([c['raw'] for c in load_cases(path)], ['🔥 Prod up', '🚀 Deploy'])


if __name__ == '__main__':
    unittest.main()
