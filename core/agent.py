import json
import os
import re
import select
import sys
import termios
import tty

from core.auditor import classify_bash_risks, explain_bash_command
from tools.tools import (
    DEFAULT_BASH_OUTPUT_CHARS,
    DEFAULT_BASH_TIMEOUT_SECONDS,
    MAX_BASH_OUTPUT_CHARS,
    MAX_BASH_TIMEOUT_SECONDS,
    TOOLS,
    bash_script,
    resolve_path,
    run_bash,
)

#MARK: GOVERNANCE

SYSTEM_PROMPT = (
    "You are NanoHarness, a general-purpose assistant. You can execute shell commands with the "
    "bash tool. Use bash if it helps you carry out a task given by the user. "
    "You're meant to be more autonomous: carry out tasks on your own with tools at your disposal rather than prompting the user. "
    "Bash commands run from the configured working directory unless you provide cwd. "
    "Relative cwd values resolve from the configured working directory. "
    "When a task needs several related shell commands, batch them in one bash call using commands. "
    "Use separate bash calls when later commands depend on earlier output you need to inspect first. "
    "If the user rejects a bash command, treat it as feedback on that specific command, not as a permanent restriction on bash. "
    "Use the rejection reason to continue."
)


class GenerationCancelled(Exception):
    pass


def get_policy(config: dict, tool_name: str) -> str:
    return config.get("policies", {}).get(tool_name, "ask")


def _rejection_reason() -> str:
    try:
        reason = input("Reason for rejection (optional): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "no reason provided"
    return reason or "no reason provided"


def check_policy(policy: str, tool_name: str, prompt: str) -> tuple[bool, str, str]:
    if policy == "allow":
        return True, "allowed", ""
    if policy == "deny":
        print(f"\033[91mblocked\033[0m: {tool_name} denied by policy")
        return False, "denied_by_policy", ""
    try:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes"):
            return True, "allowed", ""
        return False, "rejected_by_user", _rejection_reason()
    except (EOFError, KeyboardInterrupt):
        print()
        return False, "rejected_by_user", "no reason provided"

#MARK: REASONING

_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def _clean_reasoning(text: str) -> str:
    return _SYSTEM_REMINDER_RE.sub("", text)


def _first_reasoning_field(obj) -> str:
    fields = [
        getattr(obj, "reasoning_content", None),
        getattr(obj, "reasoning", None),
    ]
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict):
        fields.extend([
            extra.get("reasoning_content"),
            extra.get("reasoning"),
        ])
        details = extra.get("reasoning_details")
        if isinstance(details, list):
            fields.extend(
                item.get("text") or item.get("content")
                for item in details
                if isinstance(item, dict)
            )

    for field in fields:
        if isinstance(field, str) and field:
            return field
    return ""


def _cancel_requested() -> bool:
    if not sys.stdin.isatty():
        return False
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return False
    return sys.stdin.read(1) == "\x1b"


def _close_stream(stream) -> None:
    close = getattr(stream, "close", None)
    if close:
        close()


def _extract_delta_reasoning(delta, state: dict) -> str:
    reasoning = _clean_reasoning(_first_reasoning_field(delta))
    if not reasoning:
        return ""

    previous = state.get("last_reasoning_snapshot", "")
    if previous and reasoning.startswith(previous):
        chunk = reasoning[len(previous):]
        state["last_reasoning_snapshot"] = reasoning
        return chunk

    state["last_reasoning_snapshot"] = reasoning
    return reasoning


def _accumulate_tool_call(tool_calls: dict[int, dict], delta_tool_call) -> None:
    index = getattr(delta_tool_call, "index", 0) or 0
    current = tool_calls.setdefault(index, {
        "id": "",
        "type": "function",
        "function": {"name": "", "arguments": ""},
    })

    tc_id = getattr(delta_tool_call, "id", None)
    if tc_id:
        current["id"] = tc_id

    tc_type = getattr(delta_tool_call, "type", None)
    if tc_type:
        current["type"] = tc_type

    function = getattr(delta_tool_call, "function", None)
    if function:
        name = getattr(function, "name", None)
        if name:
            current["function"]["name"] += name
        arguments = getattr(function, "arguments", None)
        if arguments:
            current["function"]["arguments"] += arguments


def _assistant_message(content: str, tool_calls: dict[int, dict]) -> dict:
    message = {"role": "assistant", "content": content or None}
    if tool_calls:
        message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    return message


def stream_assistant_response(
    client,
    model: str,
    conversation: list[dict],
    completion_options: dict,
    show_reasoning: bool,
) -> dict:
    old_terminal_settings = None
    if sys.stdin.isatty():
        old_terminal_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin)

    content_parts: list[str] = []
    tool_calls: dict[int, dict] = {}
    reasoning_state: dict = {}
    printed_reasoning = False
    printed_content = False

    try:
        stream = client.chat.completions.create(
            model=model,
            tools=TOOLS,
            messages=conversation,
            stream=True,
            **completion_options,
        )

        for chunk in stream:
            if _cancel_requested():
                _close_stream(stream)
                raise GenerationCancelled

            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            reasoning = _extract_delta_reasoning(delta, reasoning_state)
            if show_reasoning and reasoning:
                if printed_content:
                    print()
                    printed_content = False
                if not printed_reasoning:
                    print("\033[2m\033[90mreasoning\033[0m\033[2m: ", end="", flush=True)
                    printed_reasoning = True
                print(reasoning, end="", flush=True)

            content = getattr(delta, "content", None) or ""
            if content:
                if printed_reasoning:
                    print("\033[0m")
                    printed_reasoning = False
                if not printed_content:
                    print("\033[93mAssistant\033[0m: ", end="", flush=True)
                    printed_content = True
                print(content, end="", flush=True)
                content_parts.append(content)

            for delta_tool_call in getattr(delta, "tool_calls", None) or []:
                _accumulate_tool_call(tool_calls, delta_tool_call)
    finally:
        if old_terminal_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_terminal_settings)
        if printed_reasoning:
            print("\033[0m")
        if printed_content:
            print()

    return _assistant_message("".join(content_parts), tool_calls)


def _completion_options(config: dict) -> dict:
    options = {}
    if "max_tokens" in config:
        options["max_tokens"] = config["max_tokens"]
    else:
        options["max_tokens"] = 4096

    extra_body = config.get("extra_body", {})
    if config.get("reasoning") is not None:
        extra_body = dict(extra_body)
        extra_body["reasoning"] = config["reasoning"]
    if extra_body:
        options["extra_body"] = extra_body
    return options


#MARK: AGENT


def bash_permission_prompt(commands: list[str], script: str, cwd: str, timeout_seconds: int, max_output_chars: int, risks: list[str], explanation: str, stop_on_error: bool) -> str:
    risk_color = "\033[93m" if risks != ["no obvious high-risk pattern detected"] else "\033[92m"
    command_block = "\n".join(f"{i}. {command}" for i, command in enumerate(commands, 1)) if len(commands) > 1 else script
    command_label = "Commands" if len(commands) > 1 else "Command"
    return (
        "\nThe assistant wants to run shell commands.\n\n"
        "Auditor explanation:\n"
        f"  {explanation}\n\n"
        "Working directory:\n"
        f"  {cwd}\n\n"
        "Risk hints:\n"
        f"  {risk_color}{', '.join(risks)}\033[0m\n\n"
        f"{command_label}:\n"
        "---\n"
        f"{command_block}\n"
        "---\n\n"
        f"Stop on error: {'yes' if stop_on_error else 'no'}\n"
        f"Timeout: {timeout_seconds} seconds\n"
        f"Output limit: {max_output_chars} characters each for stdout/stderr\n\n"
        "Allow this shell request? [y/n]: "
    )


def _bash_args(arguments: str, config: dict) -> dict:
    args = json.loads(arguments)
    bash_config = config.get("bash", {})
    timeout_seconds = args.get(
        "timeout_seconds",
        bash_config.get("timeout_seconds", DEFAULT_BASH_TIMEOUT_SECONDS),
    )
    max_output_chars = args.get(
        "max_output_chars",
        bash_config.get("max_output_chars", DEFAULT_BASH_OUTPUT_CHARS),
    )
    args["timeout_seconds"] = max(1, min(int(timeout_seconds), MAX_BASH_TIMEOUT_SECONDS))
    args["max_output_chars"] = max(1, min(int(max_output_chars), MAX_BASH_OUTPUT_CHARS))
    script, commands, stop_on_error = bash_script(args)
    args["command"] = script
    args["_commands"] = commands
    args["_stop_on_error"] = stop_on_error
    return args

def _working_directory(config: dict) -> tuple[str, str | None]:
    configured = config.get("working_directory", ".")
    if not isinstance(configured, str) or not configured.strip():
        configured = "."
    resolved = resolve_path(configured)
    if not os.path.isdir(resolved):
        return resolve_path("."), f"configured working_directory is invalid: {configured}; using launch directory"
    return resolved, None


def execute_tool(name: str, arguments: str, config: dict, client, auditor_model: str) -> str:
    if name != "bash":
        return f"error: unknown tool '{name}'. Use bash instead."

    try:
        args = _bash_args(arguments, config)
    except Exception as e:
        return f"error: invalid tool arguments: {e}"

    policy = get_policy(config, name)
    command = args["command"]
    commands = args["_commands"]
    stop_on_error = args["_stop_on_error"]
    base_cwd, cwd_warning = _working_directory(config)
    cwd = resolve_path(args.get("cwd"), base_cwd)
    risks = classify_bash_risks(command)
    try:
        explanation = explain_bash_command(client, auditor_model, commands, command, cwd, risks)
    except Exception as e:
        return f"error: could not audit command before execution: {e}"
    prompt = bash_permission_prompt(
        commands,
        command,
        cwd,
        args["timeout_seconds"],
        args["max_output_chars"],
        risks,
        (explanation or "The auditor did not return an explanation.") + (f" Warning: {cwd_warning}" if cwd_warning else ""),
        stop_on_error,
    )

    allowed, reason, rejection_reason = check_policy(policy, name, prompt)
    if not allowed:
        if reason == "denied_by_policy":
            return "permission_denied: the bash tool is disabled by policy and cannot be used."
        return (
            "rejected_by_user: The user rejected this specific bash command. "
            f"Reason: {rejection_reason}. "
            "Continue working toward the user's original goal, the rejection reason might include instructions consider them. Bash remains available."
        )

    try:
        return run_bash(
            args["command"],
            args.get("cwd"),
            args["timeout_seconds"],
            args["max_output_chars"],
            base_cwd,
        )
    except Exception as e:
        return f"error: {e}"
