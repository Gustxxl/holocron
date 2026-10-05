import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.excalidraw import (
    strip_emoji, clean, decompress_from_base64, compress_to_base64,
    load_cases, update_text, SceneError, _validate_md, _backup
)


class TestStripEmoji:
    def test_plain_text(self):
        assert strip_emoji('hello world') == 'hello world'

    def test_with_emoji(self):
        result = strip_emoji('hello 🌍 world')
        assert 'hello' in result
        assert 'world' in result

    def test_preserves_newlines(self):
        assert strip_emoji('line1\nline2') == 'line1\nline2'

    def test_empty(self):
        assert strip_emoji('') == ''


class TestClean:
    def test_valid_utf8(self):
        assert clean('hello') == 'hello'

    def test_cyrillic(self):
        assert clean('привет') == 'привет'


class TestCompression:
    def test_round_trip_ascii(self):
        original = '{"test": "hello world"}'
        compressed = compress_to_base64(original)
        assert compressed
        decompressed = decompress_from_base64(compressed)
        assert decompressed == original

    def test_round_trip_cyrillic(self):
        original = '{"text": "привет мир"}'
        compressed = compress_to_base64(original)
        decompressed = decompress_from_base64(compressed)
        assert decompressed == original

    def test_round_trip_long(self):
        original = json.dumps({'elements': [{'id': str(i), 'text': f'item {i}'} for i in range(100)]})
        compressed = compress_to_base64(original)
        decompressed = decompress_from_base64(compressed)
        assert decompressed == original

    def test_empty(self):
        assert compress_to_base64('') is not None
        assert decompress_from_base64('') is None


class TestUpdateText:
    def _write_scene(self, tmp, elements):
        scene = {
            'type': 'excalidraw',
            'version': 2,
            'elements': elements,
            'appState': {},
            'files': {}
        }
        tmp.write_text(json.dumps(scene, ensure_ascii=False), encoding='utf-8')
        return tmp

    def test_update_existing_element(self):
        with tempfile.NamedTemporaryFile(suffix='.excalidraw', mode='w', delete=False) as f:
            path = Path(f.name)
        elements = [
            {'id': 'abc123', 'type': 'text', 'text': 'old text', 'originalText': 'old text'}
        ]
        self._write_scene(path, elements)
        update_text(str(path), 'abc123', 'new text')
        scene = json.loads(path.read_text(encoding='utf-8'))
        el = scene['elements'][0]
        assert el['text'] == 'new text'
        assert el['originalText'] == 'new text'
        path.unlink()

    def test_element_not_found(self):
        with tempfile.NamedTemporaryFile(suffix='.excalidraw', mode='w', delete=False) as f:
            path = Path(f.name)
        elements = [
            {'id': 'abc123', 'type': 'text', 'text': 'old', 'originalText': 'old'}
        ]
        self._write_scene(path, elements)
        try:
            update_text(str(path), 'nonexistent', 'new')
            assert False, 'should have raised'
        except ValueError:
            pass
        path.unlink()

    def test_does_not_modify_non_text(self):
        with tempfile.NamedTemporaryFile(suffix='.excalidraw', mode='w', delete=False) as f:
            path = Path(f.name)
        elements = [
            {'id': 'rect1', 'type': 'rectangle', 'x': 0, 'y': 0},
            {'id': 'txt1', 'type': 'text', 'text': 'keep', 'originalText': 'keep'}
        ]
        self._write_scene(path, elements)
        try:
            update_text(str(path), 'rect1', 'hack')
            assert False, 'should have raised'
        except ValueError:
            pass
        scene = json.loads(path.read_text(encoding='utf-8'))
        assert scene['elements'][0]['type'] == 'rectangle'
        path.unlink()


class TestValidateMd:
    def test_valid_json(self):
        md = '## Drawing\n```json\n{}\n```'
        _validate_md(md)

    def test_valid_compressed(self):
        md = '## Drawing\n```compressed-json\nABC\n```'
        _validate_md(md)

    def test_missing_drawing(self):
        try:
            _validate_md('```json\n{}\n```')
            assert False
        except SceneError:
            pass

    def test_missing_data(self):
        try:
            _validate_md('## Drawing\nno code block')
            assert False
        except SceneError:
            pass


class TestBackup:
    def test_creates_backup(self):
        with tempfile.NamedTemporaryFile(suffix='.md', mode='w', delete=False, encoding='utf-8') as f:
            f.write('test content')
            path = Path(f.name)
        _backup(str(path))
        backup_dir = Path(__file__).resolve().parent.parent / 'data' / 'backups'
        bak = backup_dir / path.name
        assert bak.exists()
        assert bak.read_text(encoding='utf-8') == 'test content'
        bak.unlink()
        path.unlink()
