from core import config


def _entry(cfg, key):
    sources = cfg.get('sources')
    entry = sources.get(key) if isinstance(sources, dict) else None
    return entry if isinstance(entry, dict) else {}


def _save(cfg, key, entry):
    sources = cfg.get('sources') if isinstance(cfg.get('sources'), dict) else {}
    sources[key] = entry
    cfg['sources'] = sources
    config.save(cfg)


def selected(key):
    ids = _entry(config.load(), key).get('lists')
    return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []


def default(key, lists):
    stored = _entry(config.load(), key).get('default')
    chosen = selected(key)
    ids = [l['id'] for l in lists if l['id'] in chosen]
    return stored if stored in ids else (ids[0] if ids else None)


def toggle_list(key, list_id):
    cfg = config.load()
    entry = _entry(cfg, key)
    ids = selected(key)
    if list_id in ids:
        ids.remove(list_id)
        if entry.get('default') == list_id:
            entry.pop('default')
    else:
        ids.append(list_id)
    entry['lists'] = ids
    _save(cfg, key, entry)
    return list_id in ids


def set_default(key, list_id):
    cfg = config.load()
    entry = _entry(cfg, key)
    ids = selected(key)
    if list_id not in ids:
        ids.append(list_id)
    entry['lists'] = ids
    entry['default'] = list_id
    _save(cfg, key, entry)
