from core import config


def _key(case):
    return [case.get('filepath', ''), case.get('element_id', '')]


def _load():
    raw = config.load().get('favorites')
    if not isinstance(raw, list):
        return []
    return [k for k in raw if isinstance(k, list) and len(k) == 2]


def is_pinned(case):
    return _key(case) in _load()


def toggle(case):
    keys, key = _load(), _key(case)
    pinned = key not in keys
    if pinned:
        keys.append(key)
    else:
        keys.remove(key)
    cfg = config.load()
    cfg['favorites'] = keys
    config.save(cfg)
    return pinned


def resolve(cases):
    index = {tuple(_key(c)): c for c in cases}
    return [index[tuple(k)] for k in _load() if tuple(k) in index]
