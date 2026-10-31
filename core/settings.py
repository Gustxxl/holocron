from urllib.parse import urlsplit

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


KEEPER_PORT = 11434
KEEPER_LOCAL_URL = f'http://localhost:{KEEPER_PORT}'


def normalize_server(raw):
    text = raw.strip().rstrip('/')
    typed = '://' in text
    parts = urlsplit(text if typed else f'http://{text}')
    if (not text or any(ch.isspace() for ch in text) or parts.scheme not in ('http', 'https')
            or not parts.hostname or parts.username is not None or parts.query or parts.fragment
            or parts.netloc.endswith(':') or parts.port == 0):
        raise ValueError(raw)
    netloc = parts.netloc if typed or parts.port else f'{parts.netloc}:{KEEPER_PORT}'
    return f'{parts.scheme}://{netloc}{parts.path}'


def keeper_server():
    raw = load().get('keeper_server_url')
    try:
        return normalize_server(raw) if isinstance(raw, str) and raw.strip() else ''
    except ValueError:
        return ''


def keeper_model(slot):
    return (load().get(f'keeper_{slot}_model') or '').strip()


def update_keeper_server(url):
    url = normalize_server(url) if url.strip() else ''
    cfg = load()
    if url != cfg.get('keeper_server_url'):
        cfg['keeper_server_model'] = ''
    cfg['keeper_server_url'] = url
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


PAGE_ROWS = 15
PAGE_MIN, PAGE_MAX = 5, 99


def page_rows():
    rows = load().get('page_rows')
    return rows if type(rows) is int and PAGE_MIN <= rows <= PAGE_MAX else PAGE_ROWS


def update_page_rows(rows):
    cfg = load()
    cfg['page_rows'] = rows
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
