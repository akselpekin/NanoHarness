import re


BASH_RISK_PATTERNS = {
    "deletes files": [r"\brm\b", r"\brmdir\b", r"\bshred\b"],
    "modifies files": [
        r">>",
        r"(?<![<>])>(?![>])",
        r"\btee\b",
        r"\bmv\b",
        r"\bcp\b",
        r"\bchmod\b",
        r"\bchown\b",
        r"\bmkdir\b",
        r"\btouch\b",
    ],
    "uses network": [r"\bcurl\b", r"\bwget\b", r"\bssh\b", r"\bscp\b", r"\brsync\b", r"\bnc\b"],
    "installs software": [
        r"\bpip\s+install\b",
        r"\bnpm\s+install\b",
        r"\bpnpm\s+add\b",
        r"\byarn\s+add\b",
        r"\bbrew\s+install\b",
        r"\bapt(-get)?\b",
    ],
    "uses elevated privileges": [r"\bsudo\b", r"\bsu\b"],
    "may keep running in background": [
        r"&\s*$",
        r"\bnohup\b",
        r"\bdisown\b",
        r"\bcrontab\b",
        r"\blaunchctl\b",
    ],
}


def classify_bash_risks(command: str) -> list[str]:
    risks = []
    for label, patterns in BASH_RISK_PATTERNS.items():
        if any(re.search(pattern, command) for pattern in patterns):
            risks.append(label)
    return risks or ["no obvious high-risk pattern detected"]


def explain_bash_command(client, auditor_model: str, command: str, cwd: str, risks: list[str]) -> str:
    response = client.chat.completions.create(
        model=auditor_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are NanoHarness Auditor. Explain shell commands to non-technical users. "
                    "Do not execute commands. Do not approve commands. Be factual and concise. "
                    "Use at most 70 words."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Explain what this command would do before it runs.\n"
                    f"Working directory: {cwd}\n"
                    f"Risk hints: {', '.join(risks)}\n"
                    "Command:\n"
                    f"{command}"
                ),
            },
        ],
    )
    return (response.choices[0].message.content or "").strip()
