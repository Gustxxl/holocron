import os
import tempfile
from core import system


def available():
    return system.editor() is not None


def edit_text(original):
    cmd = system.editor()
    if cmd is None:
        return None
    with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', encoding='utf-8', delete=False) as f:
        f.write(original)
        tmp = f.name
    try:
        if not system.attach([*cmd, tmp]):
            return None
        with open(tmp, encoding='utf-8') as f:
            return f.read()
    finally:
        os.unlink(tmp)
