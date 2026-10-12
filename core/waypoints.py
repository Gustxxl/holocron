import re
from core import config

KEY = 'reminder_locations'
RADIUS = 100
PROXIMITIES = ('arriving', 'leaving')
_NAME = re.compile(r'\w+')


def norm(name):
    return name.strip().lstrip('@').lower() if isinstance(name, str) else ''


def _address(text):
    return ' '.join(text.split()) if isinstance(text, str) else ''


def _record(raw):
    if isinstance(raw, str):
        raw = {'address': raw}
    if not isinstance(raw, dict) or not _address(raw.get('address')):
        return None
    radius = raw.get('radius')
    valid = isinstance(radius, (int, float)) and not isinstance(radius, bool) and radius > 0
    proximity = raw.get('proximity')
    return {
        'address': _address(raw['address']),
        'radius': int(radius) if valid else RADIUS,
        'proximity': proximity if proximity in PROXIMITIES else 'arriving',
    }


def load():
    data = config.load().get(KEY)
    points = {}
    for name, raw in (data.items() if isinstance(data, dict) else ()):
        key, rec = norm(name), _record(raw)
        if rec and _NAME.fullmatch(key):
            points[key] = rec
    return dict(sorted(points.items()))


def _save(points):
    cfg = config.load()
    cfg[KEY] = dict(sorted(points.items()))
    config.save(cfg)


def put(name, address):
    key, address = norm(name), _address(address)
    if not _NAME.fullmatch(key) or not address:
        return False
    points = load()
    points[key] = {**points.get(key, {'radius': RADIUS, 'proximity': 'arriving'}), 'address': address}
    _save(points)
    return True


def change(name, **fields):
    points = load()
    key = norm(name)
    if key not in points:
        return False
    points[key].update(fields)
    _save(points)
    return True


def rename(name, new):
    points = load()
    key, new_key = norm(name), norm(new)
    if key not in points or not _NAME.fullmatch(new_key) or (new_key != key and new_key in points):
        return False
    points[new_key] = points.pop(key)
    _save(points)
    return True


def remove(name):
    points = load()
    if points.pop(norm(name), None) is None:
        return False
    _save(points)
    return True


def valid(name):
    return bool(_NAME.fullmatch(norm(name)))


def parse_edit(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None, None, 'Name on the first line, address below'
    name = norm(lines[0])
    if not valid(name):
        return None, None, 'Name must be one word'
    return name, _address(' '.join(lines[1:])), None


def find(points, address):
    needle = _address(address).lower()
    return next((name for name, p in points.items() if needle and p['address'].lower() == needle), None)


def linked(items, points):
    found = {name: [] for name in points}
    for task in items:
        name = find(points, task.get('place'))
        if name and not task.get('done'):
            found[name].append(task)
    return found
