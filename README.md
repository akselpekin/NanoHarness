# NanoHarness

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

TODO

## Tools

The agent has three tools, matching the reference article:

- **read_file** — read the contents of a relative file path
- **list_files** — list files and directories recursively
- **edit_file** — replace one exact string match in a file, or create a new file

Tool paths are constrained to the repository workspace.

## Sessions

Chat sessions are saved as JSON files in `sessions/`. Use `/help` in the CLI to see session commands.
