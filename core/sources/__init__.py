from core import config


def _entry(cfg, key):
    sources = cfg.get('sources')
    entry = sources.get(key) if isinstance(sources, dict) else None
    return entry if isinstance(entry, dict) else {}


def selected(key):
    ids = _entry(config.load(), key).get('lists')
    return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []


def toggle_list(key, list_id):
    cfg = config.load()
    ids = selected(key)
    if list_id in ids:
        ids.remove(list_id)
    else:
        ids.append(list_id)
    entry = _entry(cfg, key)
    entry['lists'] = ids
    sources = cfg.get('sources') if isinstance(cfg.get('sources'), dict) else {}
    sources[key] = entry
    cfg['sources'] = sources
    config.save(cfg)
    return list_id in ids
