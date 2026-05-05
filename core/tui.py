import os

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from core.paths import APP_DIR


_session: PromptSession | None = None


def _prompt_session() -> PromptSession:
    global _session
    if _session is None:
        os.makedirs(APP_DIR, exist_ok=True)
        history_path = os.path.join(APP_DIR, "prompt_history.txt")
        _session = PromptSession(history=FileHistory(history_path))
    return _session


def prompt_user() -> str:
    return _prompt_session().prompt(HTML("<ansiblue>You</ansiblue>: "))
