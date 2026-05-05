import json
import os
from datetime import datetime

from core.paths import APP_DIR, CONFIG_PATH, SESSIONS_DIR


CONFIG_VERSION = "v1"

REFERENCE_CONFIG = {
    "config_version": CONFIG_VERSION,
    "api_key": "",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openai/gpt-5-nano",
    "auditor_model": "openai/gpt-5.4-nano",
    "show_reasoning": True,
    "bash": {
        "timeout_seconds": 10,
        "max_output_chars": 12000,
    },
    "policies": {
        "bash": "ask",
    },
}


def _write_config(config: dict) -> None:
    config_dir = os.path.dirname(CONFIG_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def _backup_invalid_config() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{CONFIG_PATH}.invalid.{timestamp}"
    os.replace(CONFIG_PATH, backup_path)
    return backup_path


def _merge_config(reference: dict, existing: dict) -> dict:
    merged = dict(existing)
    for key, ref_value in reference.items():
        if key == "config_version":
            merged[key] = CONFIG_VERSION
        elif key not in merged:
            merged[key] = ref_value
        elif isinstance(ref_value, dict) and isinstance(merged[key], dict):
            merged[key] = _merge_config(ref_value, merged[key])
        elif not isinstance(merged[key], type(ref_value)):
            merged[key] = ref_value
    return merged


def startup_checks() -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)

    if not os.path.exists(CONFIG_PATH):
        _write_config(REFERENCE_CONFIG)
        print(f"Created config: {CONFIG_PATH}")
        return

    try:
        with open(CONFIG_PATH) as f:
            existing = json.load(f)
    except json.JSONDecodeError:
        backup_path = _backup_invalid_config()
        _write_config(REFERENCE_CONFIG)
        print(f"Invalid config backed up: {backup_path}")
        print(f"Created config: {CONFIG_PATH}")
        return

    if not isinstance(existing, dict):
        backup_path = _backup_invalid_config()
        _write_config(REFERENCE_CONFIG)
        print(f"Invalid config backed up: {backup_path}")
        print(f"Created config: {CONFIG_PATH}")
        return

    merged = _merge_config(REFERENCE_CONFIG, existing)
    if merged != existing:
        _write_config(merged)
        print(f"Updated config schema: {CONFIG_PATH}")
