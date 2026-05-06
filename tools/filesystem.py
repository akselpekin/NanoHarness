import json
import os

from tools.common import clamp_int, resolve_path, truncate_text


DEFAULT_LIST_MAX_ENTRIES = 200
MAX_LIST_ENTRIES = 1000
DEFAULT_READ_MAX_CHARS = 20000
MAX_READ_CHARS = 100000


def list_files(args: dict, base_cwd: str) -> str:
    path = resolve_path(args.get("path", "."), base_cwd)
    if not os.path.isdir(path):
        return json.dumps({"error": f"not a directory: {args.get('path', '.')}"})

    recursive = bool(args.get("recursive", False))
    max_entries = clamp_int(args.get("max_entries"), DEFAULT_LIST_MAX_ENTRIES, 1, MAX_LIST_ENTRIES)
    entries: list[str] = []
    truncated = False

    def add_entry(full_path: str, is_dir: bool) -> bool:
        rel = os.path.relpath(full_path, path)
        entries.append(rel + "/" if is_dir else rel)
        return len(entries) >= max_entries

    if recursive:
        for root, dirs, files in os.walk(path):
            for d in dirs:
                if add_entry(os.path.join(root, d), True):
                    truncated = True
                    break
            if truncated:
                break
            for f in files:
                if add_entry(os.path.join(root, f), False):
                    truncated = True
                    break
            if truncated:
                break
    else:
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            if add_entry(full_path, os.path.isdir(full_path)):
                truncated = True
                break

    return json.dumps({"path": path, "entries": entries, "recursive": recursive, "truncated": truncated, "max_entries": max_entries})


def read_file(args: dict, base_cwd: str) -> str:
    path = resolve_path(args.get("path"), base_cwd)
    if os.path.isdir(path):
        return json.dumps({"error": f"is a directory: {args.get('path')}"})
    offset = clamp_int(args.get("offset"), 0, 0, 10**12)
    max_chars = clamp_int(args.get("max_chars"), DEFAULT_READ_MAX_CHARS, 1, MAX_READ_CHARS)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"file not found: {args.get('path')}"})
    chunk, truncated = truncate_text(content[offset:], max_chars)
    return json.dumps({"path": path, "content": chunk, "offset": offset, "max_chars": max_chars, "truncated": truncated})


def write_file(args: dict, base_cwd: str) -> str:
    path = resolve_path(args.get("path"), base_cwd)
    mode = args.get("mode")
    create_dirs = bool(args.get("create_dirs", False))
    if mode not in ("create", "overwrite", "append", "replace"):
        return json.dumps({"error": "mode must be create, overwrite, append, or replace"})
    if os.path.isdir(path):
        return json.dumps({"error": f"is a directory: {args.get('path')}"})
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        if create_dirs:
            os.makedirs(parent, exist_ok=True)
        else:
            return json.dumps({"error": f"parent directory does not exist: {parent}"})

    if mode == "create":
        if os.path.exists(path):
            return json.dumps({"error": f"file already exists: {args.get('path')}"})
        content = args.get("content", "")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"path": path, "mode": mode, "bytes_written": len(content.encode("utf-8"))})

    if mode == "overwrite":
        content = args.get("content", "")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"path": path, "mode": mode, "bytes_written": len(content.encode("utf-8"))})

    if mode == "append":
        content = args.get("content", "")
        existed = os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"path": path, "mode": mode, "created": not existed, "bytes_written": len(content.encode("utf-8"))})

    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")
    replace_all = bool(args.get("replace_all", False))
    if not old_text:
        return json.dumps({"error": "old_text is required for replace mode"})
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"file not found: {args.get('path')}"})
    count = content.count(old_text)
    if count == 0:
        return json.dumps({"error": "old_text not found"})
    if count > 1 and not replace_all:
        return json.dumps({"error": "old_text matched multiple times", "matches": count})
    new_content = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return json.dumps({"path": path, "mode": mode, "replacements": count if replace_all else 1, "bytes_written": len(new_content.encode("utf-8"))})


FILESYSTEM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories. Non-recursive by default and output capped.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path. Relative paths resolve from the configured working directory."},
                    "recursive": {"type": "boolean", "description": "Whether to list recursively. Defaults to false."},
                    "max_entries": {"type": "integer", "description": f"Maximum entries to return. Defaults to {DEFAULT_LIST_MAX_ENTRIES}, capped at {MAX_LIST_ENTRIES}."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read bounded text content from a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path. Relative paths resolve from the configured working directory."},
                    "offset": {"type": "integer", "description": "Character offset to start reading from. Defaults to 0."},
                    "max_chars": {"type": "integer", "description": f"Maximum characters to return. Defaults to {DEFAULT_READ_MAX_CHARS}, capped at {MAX_READ_CHARS}."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create, overwrite, append, or replace text in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path. Relative paths resolve from the configured working directory."},
                    "mode": {"type": "string", "description": "One of create, overwrite, append, replace."},
                    "content": {"type": "string", "description": "Content for create, overwrite, or append modes."},
                    "old_text": {"type": "string", "description": "Text to replace in replace mode."},
                    "new_text": {"type": "string", "description": "Replacement text for replace mode."},
                    "replace_all": {"type": "boolean", "description": "Replace all matches in replace mode. Defaults to false."},
                    "create_dirs": {"type": "boolean", "description": "Create parent directories if missing. Defaults to false."},
                },
                "required": ["path", "mode"],
            },
        },
    },
]


STRUCTURED_FILE_HANDLERS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
}
