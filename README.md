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

On first launch, NanoHarness creates its app directory and a starter config file.

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
/cwd             Show where relative shell paths resolve from
/config          Show app/config/session paths
```

At the prompt, arrow keys work for editing and history navigation.

## Shell Access

NanoHarness exposes one tool to the model:

- `bash` requests execution of a shell command on your machine.

Before a command runs, NanoHarness:

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

```json
#openAI reference
{
  "api_key": "",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4.1",
  "auditor_model": "gpt-4.1",
  "show_reasoning": true,
  "bash": {
    "timeout_seconds": 10,
    "max_output_chars": 12000
  },
  "policies": {
    "bash": "ask"
  }
}

#openrouter reference
REFERENCE_CONFIG = {
    "api_key": "",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openai/gpt-5.4-nano",
    "auditor_model": "openai/gpt-5.4-nano",
    "show_reasoning": True,
    "bash": {
        "timeout_seconds": 10,
        "max_output_chars": 12000,
    },
    "policies": {
        "bash": "ask",
    },
}
```

Reasoning output depends on provider and model support. If the provider does not return reasoning deltas, NanoHarness cannot display them even when `show_reasoning` is enabled.