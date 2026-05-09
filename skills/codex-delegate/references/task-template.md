# Codex task brief template

Save the brief at `.ai/codex_task_<name>.md`. If the task is part of a multi-agent run planned by `agent-task-splitter`, the brief is already at `.ai/codex_task_<NNN>_<slug>.md`; read `.coord/plan.yml` for round context first.

## Template

```markdown
# Task: <descriptive name>

## Context
- Repo: C:\path\to\repo
- Read these files first:
  - path/a.py
  - path/b.py
- Only modify:
  - path/c.py
  - path/d.py

## Goal
<what Codex should produce>

## Constraints
- Do not edit files outside the allowed list
- Follow adjacent code style
- Do not make architectural changes

## Acceptance
- Required tests: <commands>
- Required files_changed expectation: <high-level expectation>
- Required result summary: write a concise summary to .ai/codex_result_<name>.md
```

## Filling it in

- **Context** must be specific. "Read the codebase" is not specific enough.
- **Only modify** is the scope fence. If Codex writes outside it, reject the result.
- **Constraints** should call out anti-patterns you've seen Codex make, not just generic guidance.
- **Acceptance** must be a runnable command, not a vibe.

## Anti-patterns

- Vague goals ("clean up this module")
- Missing scope fence (Codex will then "improve" unrelated files)
- Acceptance written as prose instead of executable verification
- Asking Codex to "decide" between alternatives instead of just executing
