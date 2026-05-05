import os


APP_DIR = os.environ.get("NANOHARNESS_HOME", os.path.expanduser("~/.nanoharness"))
CONFIG_PATH = os.environ.get("NANOHARNESS_CONFIG", os.path.join(APP_DIR, "config.json"))
SESSIONS_DIR = os.path.join(APP_DIR, "sessions")
