import json
import os, shutil
from pathlib import Path

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
CONFIG = Path(DATA_DIR) / "config.json"
TEMPLATE = os.path.join(APP_DIR, "config.example.json")

DEFAULTS = {
    "operator_name": "",
    "excalidraw_obsidian_path": "",
}


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def ensure_config():
    ensure_data_dir()
    if not CONFIG.exists():
        shutil.copy2(TEMPLATE, CONFIG)


def load():
    ensure_data_dir()
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except Exception:
            print("error")
    return cfg


def save(cfg):
    ensure_data_dir()
    try:
        CONFIG.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"\033[31mFailed to save config: {e}\033[0m")
