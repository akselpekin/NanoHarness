# miniharness

A code-editing agent in one Python file (~170 LOC). Faithful port of [How to Build an Agent](https://ampcode.com/notes/how-to-build-an-agent) from Go/Anthropic to Python/OpenAI API standard.

## Setup

```bash
source .venv/bin/activate
pip install openai
export OPENAI_API_KEY=sk-...
python agent.py
```

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | (required) | API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `gpt-4.1` | Model to use |

## Tools

The agent has three tools, matching the reference article:

- **read_file** — read the contents of a relative file path
- **list_files** — list files and directories recursively
- **edit_file** — replace a string in a file, or create a new file
