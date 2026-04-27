#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook for Mix Analyzer.

When the user's prompt looks like an architecture / dependency / cross-module
question, inject a short reminder asking Claude to consult the knowledge graph
(graphify-out/graph.json) BEFORE grep / Read. Otherwise stay silent.

Hook contract:
- stdin: JSON with at least {"prompt": "<user text>"}
- stdout: any text printed is appended to Claude's context as a system
  reminder for the current turn
- exit 0: success (silent or with reminder)
- exit non-zero: hook is treated as failed but does not block the prompt
"""
import json
import re
import sys
from pathlib import Path


# Conservative pattern set: trigger ONLY when the prompt clearly asks about
# code structure / dependencies / flow across modules. False positives waste
# my tokens; false negatives just mean the reminder doesn't fire (the agent
# can still be invoked manually).
ARCH_PATTERNS = [
    # English
    r"\bhow does?\s+\w+\s+(work|operate|interact|connect|communicate)",
    r"\bwhere is\s+\w+\s+(used|called|defined|wired)",
    r"\bwho (uses|calls|depends on|implements)\s+\w+",
    r"\bwhat (depends on|connects?|links?|wires?)\s+\w+",
    r"\btrace\s+(the\s+)?(flow|path|chain|pipeline)",
    r"\b(architecture|dependency graph|cross[- ]module|end[- ]to[- ]end)\b",
    r"\b(pipeline|data flow|control flow)\b",
    r"\bexplain\s+(the\s+)?(architecture|pipeline|module|system|flow)",
    # French
    r"comment\s+(ça\s+)?(marche|fonctionne|s'articule|est wired|est connect[ée])",
    r"qui\s+(utilise|appelle|d[ée]pend de|impl[ée]mente)",
    r"\b(architecture|pipeline|d[ée]pendances?|cross[- ]module)\b",
    r"relation\s+entre\s+\w+\s+et\s+\w+",
    r"\b(de bout en bout|end[- ]to[- ]end)\b",
    r"explique\s+(la|le)\s+(pipeline|architecture|module|syst[èe]me|flux)",
    r"trace[rz]?\s+(le|la)\s+(flux|chemin|cha[îi]ne|pipeline)",
]

REMINDER = """[graphify auto-reminder] This prompt looks like an architecture / dependency / cross-module question. BEFORE running grep / Glob / Read, consult graphify-out/graph.json:
  - Bash("/graphify query \\"<concept>\\"")  for broad context (BFS)
  - Bash("/graphify path \\"A\\" \\"B\\"")    for the connection between two concepts
  - Bash("/graphify explain \\"X\\"")         for everything connected to X
For multi-query synthesis, delegate to the graph-first-explorer subagent (saves your context window). Skip this for trivial single-file or detailed-algorithm questions — those are cheaper as direct Read."""


def main():
    try:
        # Force UTF-8 stdin reading — on Windows the default console
        # encoding (cp1252) mangles French characters
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except Exception:
        return 0

    prompt = (data.get("prompt") or "").lower()
    if not prompt:
        return 0

    # Only fire if the project actually has a graph to consult.
    if not Path("graphify-out/graph.json").exists():
        return 0

    for pattern in ARCH_PATTERNS:
        if re.search(pattern, prompt, flags=re.IGNORECASE | re.UNICODE):
            print(REMINDER)
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
