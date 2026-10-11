import re
from pathlib import Path
from core import system


def clean_input_path(raw):
    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return ''
    if not system.IS_WINDOWS:
        raw = re.sub(r"\\(.)", r"\1", raw)
    return str(Path(raw).expanduser())
