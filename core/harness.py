import json
import os
from datetime import datetime, timezone

from core.agent import (
    SYSTEM_PROMPT,
    GenerationCancelled,
    _completion_options,
    execute_tool,
    stream_assistant_response,
)
from core.paths import APP_DIR, CONFIG_PATH, SESSIONS_DIR
from core.tui import prompt_user

#MARK: Config

def load_config(path: str = CONFIG_PATH) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"\033[91mconfiguration error\033[0m: invalid JSON in {path}")
        return {}


def save_config(config: dict, path: str = CONFIG_PATH) -> None:
    config_dir = os.path.dirname(path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def config_status(path: str = CONFIG_PATH) -> str:
    config = load_config(path)
    lines = [
        f"App home: {APP_DIR}",
        f"Sessions: {SESSIONS_DIR}",
        f"Launch directory: {os.getcwd()}",
        working_directory_status(config),
        f"Config: {path}",
    ]
    return "\n  ".join(lines)


def resolve_working_directory(config: dict, value: str | None = None) -> tuple[str, str | None]:
    configured = config.get("working_directory", ".") if value is None else value
    if not isinstance(configured, str) or not configured.strip():
        configured = "."
    expanded = os.path.expanduser(configured)
    if not os.path.isabs(expanded):
        expanded = os.path.join(os.getcwd(), expanded)
    resolved = os.path.abspath(expanded)
    if not os.path.isdir(resolved):
        return os.getcwd(), f"configured working_directory is invalid: {configured}; using launch directory"
    return resolved, None


def working_directory_status(config: dict) -> str:
    configured = config.get("working_directory", ".")
    resolved, warning = resolve_working_directory(config)
    lines = [
        f"Configured working directory: {configured}",
        f"Resolved working directory: {resolved}",
    ]
    if warning:
        lines.append(f"Warning: {warning}")
    return "\n  ".join(lines)

#MARK: API

def _api_key_status(config: dict) -> str:
    value = config.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
    source = "config" if config.get("api_key") else "OPENAI_API_KEY" if os.environ.get("OPENAI_API_KEY") else "none"
    if not value:
        return "API key: not set"
    return f"API key: set via {source} (...{value[-4:]})"

#MARK: Session

def _session_path(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, session_id + ".json")


def new_session() -> dict:
    sid = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return {
        "id": sid,
        "created": sid,
        "title": "new session",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
    }


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


def delete_all_sessions() -> int:
    count = 0
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            os.remove(os.path.join(SESSIONS_DIR, fname))
            count += 1
    return count


def list_sessions() -> list[dict]:
    sessions = []
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(SESSIONS_DIR, fname)) as f:
                    s = json.load(f)
                sessions.append(s)
            except (json.JSONDecodeError, KeyError):
                continue
    sessions.sort(key=lambda s: s.get("created", ""), reverse=True)
    return sessions

#MARK: Auto title

def _auto_title(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            text = m["content"].strip()
            return text[:50] + ("..." if len(text) > 50 else "")
    return "new session"


#MARK: Recovery

def _recover_failed_turn(conversation: list[dict], session: dict) -> None:
    if conversation and conversation[-1].get("role") == "user":
        conversation.pop()
    save_session(session)

#MARK: Command handler

def handle_command(cmd: str, session: dict, config: dict) -> tuple[dict | None, dict]:
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
        return session, config

    elif command == "/new":
        save_session(session)
        ns = new_session()
        save_session(ns)
        print(f"  New session: {ns['id']}")
        return ns, config

    elif command == "/switch":
        if not arg:
            print("  Usage: /switch <index>")
            return session, config
        sessions = list_sessions()
        try:
            idx = int(arg)
            target = sessions[idx]
        except (ValueError, IndexError):
            print(f"  Invalid index: {arg}")
            return session, config
        save_session(session)
        loaded = load_session(target["id"])
        print(f"  Switched to: {loaded['title']}  ({loaded['id']})")
        return loaded, config

    elif command == "/delete":
        if arg.strip().lower() == "all":
            try:
                answer = input("  Delete all sessions? [y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return session, config
            if answer not in ("y", "yes"):
                print("  Delete all cancelled.")
                return session, config
            count = delete_all_sessions()
            ns = new_session()
            save_session(ns)
            print(f"  Deleted {count} sessions.")
            print(f"  Started new session: {ns['id']}")
            return ns, config
        if not arg:
            print("  Usage: /delete <index|all>")
            return session, config
        sessions = list_sessions()
        try:
            idx = int(arg)
            target = sessions[idx]
        except (ValueError, IndexError):
            print(f"  Invalid index: {arg}")
            return session, config
        delete_session(target["id"])
        print(f"  Deleted: {target['title']}  ({target['id']})")
        if target["id"] == session["id"]:
            ns = new_session()
            save_session(ns)
            print(f"  Started new session: {ns['id']}")
            return ns, config
        return session, config

    elif command == "/rename":
        if not arg:
            print("  Usage: /rename <title>")
            return session, config
        session["title"] = arg
        save_session(session)
        print(f"  Renamed to: {arg}")
        return session, config

    elif command == "/help":
        print("  /sessions          List all sessions")
        print("  /new               Start a new session")
        print("  /switch <index>    Switch to a session")
        print("  /delete <index>    Delete a session")
        print("  /delete all        Delete all sessions")
        print("  /rename <title>    Rename current session")
        print("  /cwd               Show working directory status")
        print("  /cwd set <path>    Set working directory")
        print("  /config            Show config file lookup status")
        print("  /apikey            Show API key status")
        print("  /apikey set        Add or overwrite API key")
        print("  /apikey delete     Delete API key from config")
        print("  /help              Show this help")
        return session, config

    elif command == "/cwd":
        if not arg:
            print(f"  Launch directory: {os.getcwd()}")
            print(f"  {working_directory_status(config)}")
            return session, config
        parts = arg.split(None, 1)
        if parts[0].lower() == "set" and len(parts) == 2:
            candidate = parts[1].strip()
            resolved, warning = resolve_working_directory(config, candidate)
            if warning:
                print(f"  Invalid working directory: {candidate}")
                print(f"  {warning}")
                return session, config
            config["working_directory"] = candidate
            save_config(config)
            print(f"  Working directory set to: {resolved}")
            return session, config
        print("  Usage: /cwd or /cwd set <path>")
        return session, config

    elif command == "/config":
        print(f"  Config: {config_status()}")
        return session, config

    elif command == "/apikey":
        subcommand = arg.strip().lower()
        if not subcommand:
            print(f"  {_api_key_status(config)}")
            return session, config
        if subcommand in ("set", "add", "overwrite"):
            try:
                api_key = input("  New API key: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return session, config
            if not api_key:
                print("  API key unchanged: empty value")
                return session, config
            config["api_key"] = api_key
            save_config(config)
            print(f"  API key saved to {CONFIG_PATH}")
            return session, config
        if subcommand in ("delete", "remove", "clear"):
            if "api_key" in config:
                del config["api_key"]
                save_config(config)
                print(f"  API key deleted from {CONFIG_PATH}")
            else:
                print("  API key is not set in config")
            return session, config
        print("  Usage: /apikey [set|delete]")
        return session, config

    else:
        print(f"  Unknown command: {command}. Type /help for commands.")
        return session, config


#MARK: Main Loop

def run():
    from openai import APIConnectionError, APIError, AuthenticationError, OpenAI

    config = load_config()

    api_key = config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
    base_url = config.get("base_url", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    model = config.get("model", os.environ.get("OPENAI_MODEL", "gpt-4.1"))
    auditor_model = config.get("auditor_model", model)
    completion_options = _completion_options(config)
    show_reasoning = config.get("show_reasoning", True)

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception as e:
        print(f"\033[91mconfiguration error\033[0m: {e}")
        print(f"Set OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL or update {CONFIG_PATH}.")
        return

    session = new_session()
    save_session(session)
    conversation = session["messages"]

    print("Chat with the agent (ctrl-c to quit, esc to stop model, /help for commands)")

    read_user_input = True
    while True:
        if read_user_input:
            try:
                user_input = prompt_user()
            except (EOFError, KeyboardInterrupt):
                save_session(session)
                print()
                break

            if user_input.startswith("/"):
                result, config = handle_command(user_input, session, config)
                if result is None:
                    break
                if result["id"] != session["id"]:
                    session = result
                    conversation = session["messages"]
                else:
                    session = result
                continue

            if not user_input.strip():
                continue

            conversation.append({"role": "user", "content": user_input})
            session["title"] = _auto_title(conversation)

        try:
            assistant_message = stream_assistant_response(
                client,
                model,
                conversation,
                completion_options,
                show_reasoning,
            )
        except (GenerationCancelled, KeyboardInterrupt):
            print("\033[91mcancelled\033[0m: model generation stopped")
            read_user_input = True
            _recover_failed_turn(conversation, session)
            continue
        except AuthenticationError as e:
            print(f"\033[91mauthentication error\033[0m: {e}")
            print(f"Check OPENAI_API_KEY or {CONFIG_PATH}, then try another message.")
            read_user_input = True
            _recover_failed_turn(conversation, session)
            continue
        except APIConnectionError as e:
            print(f"\033[91mconnection error\033[0m: {e}")
            print("Check OPENAI_BASE_URL and your network connection, then try another message.")
            read_user_input = True
            _recover_failed_turn(conversation, session)
            continue
        except APIError as e:
            print(f"\033[91mapi error\033[0m: {e}")
            print("The provider rejected the request. Check the model, endpoint, and request settings.")
            read_user_input = True
            _recover_failed_turn(conversation, session)
            continue
        except Exception as e:
            print(f"\033[91munexpected error\033[0m: {e}")
            print("The request failed. Update your configuration if needed, then try another message.")
            read_user_input = True
            _recover_failed_turn(conversation, session)
            continue
        conversation.append(assistant_message)

        if assistant_message.get("tool_calls"):
            read_user_input = False
            for tc in assistant_message["tool_calls"]:
                function = tc["function"]
                print(f"\033[92mtool\033[0m: {function['name']}({function['arguments']})")
                result = execute_tool(function["name"], function["arguments"], config, client, auditor_model)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            read_user_input = True

        save_session(session)
