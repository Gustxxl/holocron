from core.config import load, save
from ui.interface import clear_screen
from ui.clean_path import clean_input_path


def operator_name():
    cfg = load()
    return (cfg.get('operator_name') or '').strip()


def update_operator_name(new_name):
    cfg = load()
    cfg['operator_name'] = new_name
    save(cfg)
    clear_screen()
    print('Success')


def archive_path():
    cfg = load()
    path = (cfg.get('excalidraw_obsidian_path') or '').strip()
    if path in ('', '.'):
        return ''
    return path


def update_archive_path(new_path):
    cfg = load()
    cfg['excalidraw_obsidian_path'] = clean_input_path(new_path)
    save(cfg)
    clear_screen()
    print('Success')


def excalidraw_path():
    cfg = load()
    path = (cfg.get('excalidraw_path') or '').strip()
    if path in ('', '.'):
        return ''
    return path


def update_excalidraw_path(new_path):
    cfg = load()
    cfg['excalidraw_path'] = clean_input_path(new_path)
    save(cfg)
    clear_screen()
    print('Success')


def vault_path():
    cfg = load()
    path = (cfg.get('vault_path') or '').strip()
    if path in ('', '.'):
        return ''
    return path


def update_vault_path(new_path):
    cfg = load()
    cleaned = clean_input_path(new_path)
    if cleaned != cfg.get('vault_path'):
        cfg['vault_exclude'] = []
    cfg['vault_path'] = cleaned
    save(cfg)
    clear_screen()
    print('Success')


def vault_exclude():
    items = load().get('vault_exclude')
    return [p for p in items if isinstance(p, str) and p] if isinstance(items, list) else []


def update_vault_exclude(items):
    cfg = load()
    cfg['vault_exclude'] = items
    save(cfg)


def new_cases_path():
    cfg = load()
    path = (cfg.get('new_cases_path') or '').strip()
    if path in ('', '.'):
        return ''
    return path


def update_new_cases_path(new_path):
    cfg = load()
    cfg['new_cases_path'] = clean_input_path(new_path)
    save(cfg)
    clear_screen()
    print('Success')


KEEPER_LOCAL_URL = 'http://localhost:11434'


def keeper_server():
    return (load().get('keeper_server_url') or '').strip()


def keeper_model(slot):
    return (load().get(f'keeper_{slot}_model') or '').strip()


def update_keeper_server(url):
    url = url.strip().rstrip('/')
    if url and '://' not in url:
        url = 'http://' + url
    cfg = load()
    cfg['keeper_server_url'] = url
    if not url:
        cfg['keeper_server_model'] = ''
    save(cfg)


def update_keeper_model(slot, model):
    cfg = load()
    cfg[f'keeper_{slot}_model'] = model
    save(cfg)


SEARCH_SEPARATOR = ';'


def search_separator():
    sep = load().get('search_separator')
    return sep if isinstance(sep, str) else SEARCH_SEPARATOR


def update_search_separator(sep):
    cfg = load()
    cfg['search_separator'] = sep
    save(cfg)


HOME_BLOCKS = ('calendar', 'schedule', 'reminders')


def home_order():
    items = load().get('home_order')
    items = [b for b in items if b in HOME_BLOCKS] if isinstance(items, list) else []
    items = list(dict.fromkeys(items))
    return [*items, *(b for b in HOME_BLOCKS if b not in items)]


def update_home_order(items):
    cfg = load()
    cfg['home_order'] = items
    save(cfg)


def reorder(items, text):
    picks = text.replace(' ', '')
    if not picks.isdigit() or len(set(picks)) != len(picks) or not all(1 <= int(c) <= len(items) for c in picks):
        return None
    first = [items[int(c) - 1] for c in picks]
    return [*first, *(i for i in items if i not in first)]
