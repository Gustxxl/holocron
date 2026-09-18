from core.config import load, save
from ui.interface import clear_screen


def operator_name():
    cfg = load()
    operator = (cfg.get('operator_name') or '').strip()
    return operator


def update_operator_name(new_name):
    operator = load()
    operator['operator_name'] = new_name
    save(operator)
    clear_screen()
    print('Success')
