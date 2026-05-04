import json
import os
import re
import sys
from openai import OpenAI

CONFIG_PATH = "../config/config.json"

#MARK: TOOLS

def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()


def list_files(path: str = ".") -> str:
    if not path:
        path = "."
    entries: list[str] = []
    for root, dirs, files in os.walk(path):
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), path)
            entries.append(rel + "/")
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), path)
            entries.append(rel)
    return json.dumps(entries)


def edit_file(path: str, old_str: str, new_str: str) -> str:
    if not path or old_str == new_str:
        return "error: invalid input parameters"

    try:
        content = open(path).read()
    except FileNotFoundError:
        if old_str == "":
            dir_name = os.path.dirname(path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(path, "w") as f:
                f.write(new_str)
            return f"Successfully created file {path}"
        return f"error: file not found: {path}"

    if old_str not in content and old_str != "":
        return "error: old_str not found in file"

    new_content = content.replace(old_str, new_str)
    with open(path, "w") as f:
        f.write(new_content)
    return "OK"


#MARK: TOOL DEFINES
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a given relative file path. "
                "Use this when you want to see what's inside a file. "
                "Do not use this with directory names."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path of a file in the working directory.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files and directories at a given path. "
                "If no path is provided, lists files in the current directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional relative path to list files from. "
                            "Defaults to current directory if not provided."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Make edits to a text file.\n\n"
                "Replaces 'old_str' with 'new_str' in the given file. "
                "'old_str' and 'new_str' MUST be different from each other.\n\n"
                "If the file specified with path doesn't exist, it will be created."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Text to search for - must match exactly and must only have one match exactly",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Text to replace old_str with",
                    },
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "read_file": lambda args: read_file(args["path"]),
    "list_files": lambda args: list_files(args.get("path", ".")),
    "edit_file": lambda args: edit_file(args["path"], args["old_str"], args["new_str"]),
}

#MARK: GOVERNANCE

DEFAULT_POLICIES = {
    "read_file": "deny",
    "list_files": "deny",
    "edit_file": "deny",
}

def load_config(path: str = CONFIG_PATH) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"policies": dict(DEFAULT_POLICIES)}


def get_policy(config: dict, tool_name: str) -> str:
    return config.get("policies", {}).get(
        tool_name, DEFAULT_POLICIES.get(tool_name, "ask")
    )


def check_policy(policy: str, tool_name: str, arguments: str) -> bool:
    if policy == "allow":
        return True
    if policy == "deny":
        print(f"\033[91mblocked\033[0m: {tool_name} denied by policy")
        return False
    # policy == "ask"
    try:
        answer = input(f"\033[93mAllow {tool_name}({arguments})? [y/n]\033[0m: ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False

#MARK: SESSIONS

SESSIONS_DIR = "sessions"

from datetime import datetime, timezone


def _sessions_dir() -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return SESSIONS_DIR


def _session_path(session_id: str) -> str:
    return os.path.join(_sessions_dir(), session_id + ".json")


def new_session() -> dict:
    sid = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return {"id": sid, "created": sid, "title": "new session", "messages": []}


def save_session(session: dict) -> None:
    with open(_session_path(session["id"]), "w") as f:
        json.dump(session, f, indent=2)


def load_session(session_id: str) -> dict:
    with open(_session_path(session_id)) as f:
        return json.load(f)


def delete_session(session_id: str) -> None:
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)


def list_sessions() -> list[dict]:
    d = _sessions_dir()
    sessions = []
    for fname in os.listdir(d):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(d, fname)) as f:
                    s = json.load(f)
                sessions.append(s)
            except (json.JSONDecodeError, KeyError):
                continue
    sessions.sort(key=lambda s: s.get("created", ""), reverse=True)
    return sessions


def _auto_title(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            text = m["content"].strip()
            return text[:50] + ("..." if len(text) > 50 else "")
    return "new session"

#MARK: REASONING

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _extract_reasoning(message) -> tuple[str, str]:
    reasoning = ""
    content = message.content or ""

    rc = getattr(message, "reasoning_content", None)
    if rc:
        reasoning = rc

    think_matches = _THINK_RE.findall(content)
    if think_matches:
        tag_reasoning = "\n".join(m.strip() for m in think_matches)
        reasoning = (reasoning + "\n" + tag_reasoning).strip() if reasoning else tag_reasoning
        content = _THINK_RE.sub("", content).strip()

    return reasoning, content


def _print_reasoning(reasoning: str) -> None:
    if reasoning:
        print(f"\033[2m\033[90mreasoning\033[0m\033[2m: {reasoning}\033[0m")


#MARK: AGENT

def execute_tool(name: str, arguments: str, config: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'"

    policy = get_policy(config, name)
    if not check_policy(policy, name, arguments):
        return "error: tool call denied by policy"

    try:
        args = json.loads(arguments)
        return fn(args)
    except Exception as e:
        return f"error: {e}"


def handle_command(cmd: str, session: dict) -> dict | None:
    parts = cmd.strip().split(None, 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command == "/sessions":
        sessions = list_sessions()
        if not sessions:
            print("  No saved sessions.")
        else:
            for i, s in enumerate(sessions):
                marker = " *" if s["id"] == session["id"] else ""
                print(f"  [{i}] {s['title']}  ({s['id']}){marker}")
        return session

    elif command == "/new":
        save_session(session)
        ns = new_session()
        save_session(ns)
        print(f"  New session: {ns['id']}")
        return ns

    elif command == "/switch":
        if not arg:
            print("  Usage: /switch <index>")
            return session
        sessions = list_sessions()
        try:
            idx = int(arg)
            target = sessions[idx]
        except (ValueError, IndexError):
            print(f"  Invalid index: {arg}")
            return session
        save_session(session)
        loaded = load_session(target["id"])
        print(f"  Switched to: {loaded['title']}  ({loaded['id']})")
        return loaded

    elif command == "/delete":
        if not arg:
            print("  Usage: /delete <index>")
            return session
        sessions = list_sessions()
        try:
            idx = int(arg)
            target = sessions[idx]
        except (ValueError, IndexError):
            print(f"  Invalid index: {arg}")
            return session
        delete_session(target["id"])
        print(f"  Deleted: {target['title']}  ({target['id']})")
        if target["id"] == session["id"]:
            ns = new_session()
            save_session(ns)
            print(f"  Started new session: {ns['id']}")
            return ns
        return session

    elif command == "/rename":
        if not arg:
            print("  Usage: /rename <title>")
            return session
        session["title"] = arg
        save_session(session)
        print(f"  Renamed to: {arg}")
        return session

    elif command == "/help":
        print("  /sessions          List all sessions")
        print("  /new               Start a new session")
        print("  /switch <index>    Switch to a session")
        print("  /delete <index>    Delete a session")
        print("  /rename <title>    Rename current session")
        print("  /help              Show this help")
        return session

    else:
        print(f"  Unknown command: {command}. Type /help for commands.")
        return session


def run():
    config = load_config()

    api_key = config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
    base_url = config.get("base_url", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    model = config.get("model", os.environ.get("OPENAI_MODEL", "gpt-4.1"))

    client = OpenAI(api_key=api_key, base_url=base_url)

    session = new_session()
    save_session(session)
    conversation = session["messages"]

    print("Chat with the agent (ctrl-c to quit, /help for commands)")

    read_user_input = True
    while True:
        if read_user_input:
            try:
                user_input = input("\033[94mYou\033[0m: ")
            except (EOFError, KeyboardInterrupt):
                save_session(session)
                print()
                break

            if user_input.startswith("/"):
                result = handle_command(user_input, session)
                if result is None:
                    break
                if result["id"] != session["id"]:
                    session = result
                    conversation = session["messages"]
                else:
                    session = result
                continue

            conversation.append({"role": "user", "content": user_input})
            session["title"] = _auto_title(conversation)

        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            tools=TOOLS,
            messages=conversation,
        )
        message = response.choices[0].message

        conversation.append(message.model_dump(exclude_none=True))

        reasoning, content = _extract_reasoning(message)
        _print_reasoning(reasoning)

        if content:
            print(f"\033[93mAssistant\033[0m: {content}")

        if message.tool_calls:
            read_user_input = False
            for tc in message.tool_calls:
                print(f"\033[92mtool\033[0m: {tc.function.name}({tc.function.arguments})")
                result = execute_tool(tc.function.name, tc.function.arguments, config)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            read_user_input = True

        save_session(session)


if __name__ == "__main__":
    run()
