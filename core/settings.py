from core.config import load, save
from ui.interface import clear_screen
from ui.clean_path import clean_input_path
import os


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
    cfg['vault_path'] = clean_input_path(new_path)
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
