import os

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from core.paths import APP_DIR


MAX_HISTORY_ENTRIES = 500
MAX_HISTORY_BYTES = 200_000

_session: PromptSession | None = None


def _history_path() -> str:
    return os.path.join(APP_DIR, "prompt_history.txt")


def _prune_history(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    blocks = []
    current = []
    for line in content.splitlines(keepends=True):
        if line.startswith("#") and current:
            blocks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("".join(current))

    pruned = "".join(blocks[-MAX_HISTORY_ENTRIES:])
    if len(pruned.encode("utf-8")) > MAX_HISTORY_BYTES:
        encoded = pruned.encode("utf-8")[-MAX_HISTORY_BYTES:]
        pruned = encoded.decode("utf-8", errors="ignore")
        first_newline = pruned.find("\n")
        if first_newline != -1:
            pruned = pruned[first_newline + 1:]

    if pruned != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(pruned)


def _prompt_session() -> PromptSession:
    global _session
    if _session is None:
        os.makedirs(APP_DIR, exist_ok=True)
        history_path = _history_path()
        _prune_history(history_path)
        _session = PromptSession(history=FileHistory(history_path))
    return _session


def prompt_user() -> str:
    text = _prompt_session().prompt(HTML("<ansiblue>You</ansiblue>: "))
    _prune_history(_history_path())
    return text
