import json
import os

from core.paths import APP_DIR, CONFIG_PATH, SESSIONS_DIR


REFERENCE_CONFIG = {
    "api_key": "",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openai/gpt-5.4-nano",
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


def startup_checks() -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)

    if not os.path.exists(CONFIG_PATH):
        config_dir = os.path.dirname(CONFIG_PATH)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(REFERENCE_CONFIG, f, indent=2)
            f.write("\n")
        print(f"Created config: {CONFIG_PATH}")
