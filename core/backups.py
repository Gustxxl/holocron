import glob
import hashlib
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / 'data' / 'backups'
DAYS = 30
MAX_BYTES = 100 * 1024 * 1024

_STAMP_RE = re.compile(r'\.\d{8}-\d{6}-\d{6}\.bak$')


def _prefix(path):
    digest = hashlib.sha1(str(path.resolve()).encode('utf-8')).hexdigest()[:8]
    return f'{path.name}.{digest}'


def save(filepath):
    path = Path(filepath)
    if not path.is_file():
        return None
    DIR.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    prefix = _prefix(path)
    old = sorted(DIR.glob(f'{glob.escape(prefix)}.*.bak'))
    if old and old[-1].read_bytes() == data:
        return old[-1]
    at = datetime.now()
    target = DIR / f'{prefix}.{at:%Y%m%d-%H%M%S-%f}.bak'
    while target.exists():
        at += timedelta(microseconds=1)
        target = DIR / f'{prefix}.{at:%Y%m%d-%H%M%S-%f}.bak'
    target.write_bytes(data)
    prune(keep=target)
    return target


def prune(keep=None, now=None):
    if not DIR.is_dir():
        return
    now = now or time.time()
    files = []
    for f in DIR.iterdir():
        try:
            st = f.stat()
        except OSError:
            continue
        if f.is_file():
            files.append((st.st_mtime, st.st_size, f))
    files.sort(key=lambda x: x[0])
    newest = {}
    for _, _, f in files:
        if _STAMP_RE.search(f.name):
            newest[_STAMP_RE.sub('', f.name)] = f
    spare = {*newest.values(), keep}
    left = []
    for mtime, size, f in files:
        if now - mtime > DAYS * 86400 and f not in spare:
            f.unlink(missing_ok=True)
        else:
            left.append((size, f))
    total = sum(size for size, _ in left)
    for size, f in left:
        if total <= MAX_BYTES:
            break
        if f == keep:
            continue
        f.unlink(missing_ok=True)
        total -= size
