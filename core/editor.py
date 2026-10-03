import os
import tempfile

def edit_text(original):
    editor = os.environ.get('EDITOR', 'nano')
    with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                      encoding='utf-8', delete=False) as f:
        f.write(original)
        tmp = f.name
    try:
        os.system(f'{editor} {tmp}')
        with open(tmp, encoding='utf-8') as f:
            return f.read()
    finally:
        os.unlink(tmp)
