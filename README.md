# NanoHarness

NanoHarness is a compact terminal assistant that can answer questions, remember chat sessions, and request permission to run shell commands on your machine.

It is designed as a general-purpose assistant.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On first launch, NanoHarness creates its app directory and a starter config file. On later launches, it checks the config shape and adds missing fields after app updates without overwriting your existing settings.

## App Data

By default, NanoHarness stores its files outside the source folder:

- Config: `~/.nanoharness/config.json`
- Sessions: `~/.nanoharness/sessions/`
- Prompt history: `~/.nanoharness/prompt_history.txt`

You can override these locations:

- `NANOHARNESS_HOME` sets the app data directory.
- `NANOHARNESS_CONFIG` sets the config file path.

Use `/config` in the app to see the active paths.

## API Key

You can manage the API key from inside the app:

```text
/apikey          Show API key status
/apikey set      Add or overwrite API key
/apikey delete   Delete API key from config
```

## Commands

Type `/help` inside NanoHarness to see available commands.

Common commands:

```text
/sessions        List saved sessions
/new             Start a new session
/switch <index>  Switch to a session
/delete <index>  Delete a session
/rename <title>  Rename current session
/cwd             Show working directory status
/cwd set <path>  Set working directory
/config          Show app/config/session paths
/summarize       Summarize current session
/summary         Show current session summary
/summary clear   Clear current session summary
```

At the prompt, arrow keys work for editing and history navigation.

## Tools

NanoHarness exposes structured tools to the model:

- `list_files` lists files and directories with capped output.
- `read_file` reads bounded text content from a file.
- `write_file` creates, overwrites, appends, or replaces text in a file.
- `read_document` extracts bounded text from text-based PDFs and text-like files.
- `web_search` searches the web for relevant pages using a best-effort DuckDuckGo HTML search.
- `fetch_url` fetches text from an HTTP or HTTPS URL with GET.
- `bash` requests execution of a shell command on your machine.

Structured file and HTTP tools ask for approval directly. Before a Bash command runs, NanoHarness:

1. Asks the auditor model to explain the command in plain language.
2. Shows local risk hints.
3. Shows the command, working directory, timeout, and output limit.
4. Asks for your approval.

Commands are not run unless you approve them.

## Streaming And Cancellation

NanoHarness streams model output as it is generated.

During streamed output:

- Press `Esc` to stop the current generation and return to the prompt.
- Press `Ctrl-C` to cancel the current generation.

At the input prompt, `Ctrl-C` exits the app.

## Config Options

Important `config.json` fields:

OpenAI-compatible example:

```json
{
  "api_key": "",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-5.4-nano",
  "auditor_model": "gpt-5.4-nano",
  "summary_model": "gpt-5.4-nano",
  "working_directory": ".",
  "show_reasoning": true,
  "bash": {
    "timeout_seconds": 10,
    "max_output_chars": 12000
  },
  "context": {
    "recent_messages": 40,
    "max_tool_output_chars": 8000,
    "max_message_chars": 20000,
    "auto_summarize": false,
    "summarize_after_messages": 80
  },
  "policies": {
    "bash": "ask",
    "list_files": "ask",
    "read_file": "ask",
    "write_file": "ask",
    "read_document": "ask",
    "web_search": "ask",
    "fetch_url": "ask"
  }
}
```

OpenRouter example:

```json
{
  "api_key": "",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "openai/gpt-5.4-nano",
  "auditor_model": "openai/gpt-5.4-nano",
  "summary_model": "openai/gpt-5.4-nano",
  "working_directory": ".",
  "show_reasoning": true,
  "bash": {
    "timeout_seconds": 10,
    "max_output_chars": 12000
  },
  "context": {
    "recent_messages": 40,
    "max_tool_output_chars": 8000,
    "max_message_chars": 20000,
    "auto_summarize": false,
    "summarize_after_messages": 80
  },
  "policies": {
    "bash": "ask",
    "list_files": "ask",
    "read_file": "ask",
    "write_file": "ask",
    "read_document": "ask",
    "web_search": "ask",
    "fetch_url": "ask"
  }
}
```

Reasoning output depends on provider and model support. If the provider does not return reasoning deltas, NanoHarness cannot display them even when `show_reasoning` is enabled.
