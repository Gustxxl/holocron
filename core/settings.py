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
