import json
import os, shutil
from pathlib import Path


CONFIG_PATH = Path("data/config.json")

DEFAULTS = {
    "operator_name": ""
}

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(APP_DIR, "data")
CONFIG = os.path.join(DATA_DIR, "config.json")
TEMPLATE = os.path.join(APP_DIR, "config.example.json")

def ensure_config():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG):
        shutil.copy2(TEMPLATE, CONFIG)


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load():
    ensure_data_dir()
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg.update(saved)
        except Exception:
            print("error")
    return cfg

def save(cfg):
    ensure_data_dir()
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"\033[31mFailed to save config: {e}\033[0m")
