import os


def resolve_path(path: str | None = None, base: str | None = None) -> str:
    if not path:
        path = "."
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        expanded = os.path.join(base or os.getcwd(), expanded)
    return os.path.abspath(expanded)


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n...[truncated]", True


def clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))
