from core import config, zones

KEY = 'clocks'
NAME_MAX = 24


def _name(raw, zone):
    name = ' '.join(raw.split())[:NAME_MAX] if isinstance(raw, str) else ''
    return name or zones.label(zone)


def load():
    raw = config.load().get(KEY)
    return [{'name': _name(c.get('name'), c['zone']), 'zone': c['zone']}
            for c in (raw if isinstance(raw, list) else [])
            if isinstance(c, dict) and zones.valid(c.get('zone'))]


def _save(items):
    cfg = config.load()
    cfg[KEY] = items
    config.save(cfg)


def add(zone, name=''):
    if not zones.valid(zone):
        return False
    _save([*load(), {'name': _name(name, zone), 'zone': zone}])
    return True


def remove(n):
    items = load()
    if not 1 <= n <= len(items):
        return False
    _save(items[:n - 1] + items[n:])
    return True


def line(items, now=None):
    return '   '.join(f'{c["name"]} {zones.clock(c["zone"], now)}' for c in items if zones.get(c['zone']))
