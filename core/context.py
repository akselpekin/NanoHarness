import copy
import json


DEFAULT_CONTEXT = {
    "recent_messages": 40,
    "max_tool_output_chars": 8000,
    "max_message_chars": 20000,
    "auto_summarize": False,
    "summarize_after_messages": 80,
}


def _context_config(config: dict) -> dict:
    return {**DEFAULT_CONTEXT, **config.get("context", {})}


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated for context]"


def _truncate_message(message: dict, config: dict) -> dict:
    ctx = _context_config(config)
    msg = copy.deepcopy(message)
    content = msg.get("content")
    if isinstance(content, str):
        limit = ctx["max_tool_output_chars"] if msg.get("role") == "tool" else ctx["max_message_chars"]
        msg["content"] = _truncate_text(content, int(limit))
    return msg


def _recent_messages(messages: list[dict], count: int) -> list[dict]:
    recent = messages[-count:] if count > 0 else []
    while recent and recent[0].get("role") == "tool":
        recent = recent[1:]
    return recent


def build_context(session: dict, config: dict) -> list[dict]:
    ctx = _context_config(config)
    messages = session.get("messages", [])
    system = messages[:1]
    recent = _recent_messages(messages[1:], int(ctx["recent_messages"]))

    context = list(system)
    summary = session.get("summary")
    if summary:
        context.append({
            "role": "system",
            "content": "Session summary so far:\n" + summary,
        })
    context.extend(_truncate_message(m, config) for m in recent)
    return context


def summarize_session(client, model: str, session: dict) -> str:
    transcript = json.dumps(session.get("messages", []), ensure_ascii=False)
    response = client.chat.completions.create(
        model=model,
        max_tokens=1200,
        messages=[
            {
                "role": "system",
                "content": (
                    "Summarize this NanoHarness session for future context. Preserve user goals, "
                    "decisions, active tasks, important files/modules, rejected approaches, bugs, "
                    "configuration assumptions, and next steps. Be concise but complete."
                ),
            },
            {"role": "user", "content": transcript},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def should_auto_summarize(session: dict, config: dict) -> bool:
    ctx = _context_config(config)
    count = len(session.get("messages", []))
    return (
        bool(ctx["auto_summarize"])
        and count >= int(ctx["summarize_after_messages"])
        and count > int(session.get("summary_message_count", 0))
    )
