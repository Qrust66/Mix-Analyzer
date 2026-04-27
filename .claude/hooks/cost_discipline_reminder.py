#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook for Mix Analyzer.

Detects user prompts that exhibit known token-waste risk patterns
(open scope, scale-without-pilot signals, etc.) and injects a short
reminder pointing at .claude/COST_DISCIPLINE.md.

Conservative on purpose — false positives nag the user, false negatives
just mean Claude has to remember on its own (which the memory and the
project doc reinforce).

Hook contract: stdin is JSON with at least {"prompt": "..."}. Anything
printed on stdout is appended to Claude's context as a system reminder
for the current turn. Exit 0 always (failures stay silent).
"""
import json
import re
import sys
from pathlib import Path


# Patterns that historically led to token waste in this project's
# sessions (see memory/cost_discipline.md for the incidents).
RISK_PATTERNS = {
    "scale_without_pilot": [
        # User asks for a large batch up-front without asking for a pilot
        r"\b(fais|produis|génère|écris|écrit|crée|create)\s+\w+\s+pour\s+(tous|chaque|les\s+\d+|tout)",
        r"\bfor\s+(all|every|each|the\s+\d+)\s+\w+",
        r"\b(do|run|process)\s+(all|every|each)\s+\w+\s+(songs?|files?|drafts?|agents?)",
    ],
    "open_brief": [
        # Vague unbounded directive
        r"\bvas[- ]?y\s*,?\s*(soit|sois)\s+innovant",
        r"\bbe\s+(creative|innovative)",
        r"\bsurprise[- ]me\b",
        r"\bdo\s+your\s+best\s+work\b",
    ],
    "long_response_invitation": [
        # Phrasing that makes Claude prone to writing walls
        r"\bexplique[- ]moi\s+(en\s+détail|exhaustivement|complètement)",
        r"\bexplain\s+(in\s+detail|exhaustively|completely)\b",
    ],
}


REMINDERS = {
    "scale_without_pilot": (
        "[cost-discipline] Detected a scale-without-pilot signal. Before "
        "producing N similar files: produce 1-2 short pilots, ask the user "
        "to validate the format, THEN scale. (Rule 3 of "
        ".claude/COST_DISCIPLINE.md.)"
    ),
    "open_brief": (
        "[cost-discipline] Detected an open / unbounded brief. Before "
        "executing: cadre le scope (in-scope = X, out-of-scope = Y) and "
        "ask the user to confirm. Avoid producing speculative output that "
        "may be rejected. (Rules 1 + 4 of .claude/COST_DISCIPLINE.md.)"
    ),
    "long_response_invitation": (
        "[cost-discipline] User asked for a long/detailed answer. That's "
        "fine — but skip filler. Stay structured and dense. Default still "
        "<800 words unless the topic genuinely needs more. (Rule 1 of "
        ".claude/COST_DISCIPLINE.md.)"
    ),
}


def main():
    try:
        # Force UTF-8 stdin reading — on Windows the default console
        # encoding (cp1252) mangles French characters like ç, é, à
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except Exception:
        return 0

    prompt = (data.get("prompt") or "").lower()
    if not prompt:
        return 0

    triggered = []
    for category, patterns in RISK_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, prompt, flags=re.IGNORECASE | re.UNICODE):
                triggered.append(category)
                break  # one match per category is enough

    # Only fire if the project has the cost-discipline doc — otherwise
    # the reminder points nowhere useful.
    if not Path(".claude/COST_DISCIPLINE.md").exists():
        return 0

    if triggered:
        for cat in triggered:
            print(REMINDERS[cat])

    return 0


if __name__ == "__main__":
    sys.exit(main())
