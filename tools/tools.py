import json
import os
import subprocess

#MARK: BASH TOOL

DEFAULT_BASH_TIMEOUT_SECONDS = 10
MAX_BASH_TIMEOUT_SECONDS = 60
DEFAULT_BASH_OUTPUT_CHARS = 12000
MAX_BASH_OUTPUT_CHARS = 50000


def resolve_path(path: str | None = None, base: str | None = None) -> str:
    if not path:
        path = "."
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        expanded = os.path.join(base or os.getcwd(), expanded)
    return os.path.abspath(expanded)


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n...[truncated]", True


def bash_script(args: dict) -> tuple[str, list[str], bool]:
    commands = args.get("commands")
    if commands:
        if not isinstance(commands, list) or not all(isinstance(c, str) and c.strip() for c in commands):
            raise ValueError("commands must be a non-empty list of strings")
        stop_on_error = args.get("stop_on_error", True)
        command = "\n".join(commands)
        if stop_on_error:
            command = "set -e\n" + command
        return command, commands, stop_on_error

    command = args.get("command", "")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command is required when commands is not provided")
    return command, [command], False


def run_bash(
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    max_output_chars: int = DEFAULT_BASH_OUTPUT_CHARS,
    base_cwd: str | None = None,
) -> str:
    if not command or not command.strip():
        return json.dumps({"error": "empty command"})

    resolved_cwd = resolve_path(cwd, base_cwd)
    if not os.path.isdir(resolved_cwd):
        return json.dumps({"error": f"not a directory: {cwd or '.'}"})

    timeout_seconds = max(1, min(int(timeout_seconds), MAX_BASH_TIMEOUT_SECONDS))
    max_output_chars = max(1, min(int(max_output_chars), MAX_BASH_OUTPUT_CHARS))

    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            cwd=resolved_cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        stdout, stdout_truncated = _truncate(result.stdout, max_output_chars)
        stderr, stderr_truncated = _truncate(result.stderr, max_output_chars)
        return json.dumps({
            "exit_code": result.returncode,
            "cwd": resolved_cwd,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "timeout_seconds": timeout_seconds,
            "max_output_chars": max_output_chars,
        })
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        stdout, stdout_truncated = _truncate(stdout, max_output_chars)
        stderr, stderr_truncated = _truncate(stderr, max_output_chars)
        return json.dumps({
            "error": "timeout",
            "message": f"Command exceeded {timeout_seconds} seconds and was stopped.",
            "cwd": resolved_cwd,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "timeout_seconds": timeout_seconds,
            "max_output_chars": max_output_chars,
        })


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Request execution of a shell command on the user's machine."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "A single shell command or multi-line Bash script to run.",
                    },
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of shell commands to run as one batch. Prefer this for related commands that should be approved together.",
                    },
                    "stop_on_error": {
                        "type": "boolean",
                        "description": "When using commands, stop the batch if any command fails. Defaults to true.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory. Relative paths resolve from the configured working directory.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": f"Optional timeout in seconds. Defaults to {DEFAULT_BASH_TIMEOUT_SECONDS} and is capped at {MAX_BASH_TIMEOUT_SECONDS}.",
                    },
                    "max_output_chars": {
                        "type": "integer",
                        "description": f"Optional output character limit for stdout and stderr. Defaults to {DEFAULT_BASH_OUTPUT_CHARS} and is capped at {MAX_BASH_OUTPUT_CHARS}.",
                    },
                },
                "required": [],
            },
        },
    }
]
