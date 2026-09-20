import os
import re
from pathlib import Path


def clean_input_path(raw):
    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return ''
    if os.name != 'nt':
        raw = re.sub(r"\\(.)", r"\1", raw)
    return str(Path(raw).expanduser())
