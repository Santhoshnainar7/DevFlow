"""
Utility script to synchronize DevFlow's Phase 03 system instructions
with the active Switch Console agent configuration.
"""

import json
from pathlib import Path

WATCHER_CONFIG = Path(
    r"C:\Users\santh\AppData\Roaming\switchdash\agent-controller\servers\a9d9a453-1f5e-4518-851f-b10a41eb0ef7\watchers\e496bfd5-f2bd-40f9-8bad-fd422a31328e\config.json"
)

INSTRUCTIONS = """When a developer reports a bug:
1. Extract the issue description.
2. Classify the bug category into one of: Authentication, API failures, Database errors, Frontend issues, Validation errors, Performance problems, Dependency issues, Unknown.
3. Assess severity: Critical, High, Medium, or Low.
4. Inspect demo_repository (read-only): inspect source files, real functions, dependencies, and existing tests in demo_repository.
5. Safely attempt to reproduce where practical.
6. Identify the most likely root cause, strictly distinguishing confirmed findings from hypotheses.
7. Post the structured investigation report in this EXACT format:

Issue ID: [e.g. DF-001]
Issue title: [Title]
Bug category: [Category]
Severity: [Severity]
Description: [Description]
Affected files: [Files]
Relevant functions: [Functions]
Root cause: [Root cause]
Evidence: [Evidence]
Proposed solution: [Solution]
Testing strategy: [Strategy]
Potential risks: [Risks]

IMPORTANT RULES:
- Inspect actual repository files.
- Never invent filenames or functions.
- Distinguish confirmed findings from hypotheses.
- Do not modify source files during investigation.
- Do not claim successful reproduction unless it actually occurred.
- Do not generate fake stack traces.
- Handle missing repositories and unavailable files gracefully.
- Do not implement fixes yet. Wait for human approval."""


def update_config():
    if not WATCHER_CONFIG.exists():
        print(f"Config path {WATCHER_CONFIG} does not exist.")
        return

    with open(WATCHER_CONFIG, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "execution" in data:
        data["execution"]["instructions"] = INSTRUCTIONS
        escaped_inst = json.dumps(INSTRUCTIONS)
        data["execution"]["codexConfig"] = f'sandbox_mode = "workspace-write"\ndeveloper_instructions = {escaped_inst}\n'

    with open(WATCHER_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("Switch agent instructions successfully synchronized for Phase 03.")


if __name__ == "__main__":
    update_config()

