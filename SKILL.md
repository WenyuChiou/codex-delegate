---
name: codex-delegate
description: Use when a coding task is implementation-heavy, repetitive, or spans many files, and Claude should supervise while Codex CLI executes the mechanical work. Typical triggers include batch edits, boilerplate generation, large refactors with clear patterns, test scaffolding, and other token-heavy coding tasks. Do not use for architecture, root-cause debugging, security judgment, or ambiguous product decisions.
---

# Codex Delegate Skill

Claude is the supervisor. Claude plans, constrains scope, reviews the diff, and verifies outcomes. Codex does the heavy writing.

## When to Use

Use this skill when the task is expensive in tokens but cheap in judgment.

| Route to | Best for | Avoid |
|----------|----------|-------|
| `Codex` | Multi-file implementation, boilerplate, test scaffolds, mechanical refactors, batch edits | Architecture, debugging root cause, security review |
| `Claude` | Requirements, design, API contracts, bug diagnosis, acceptance review | Large repetitive edits |
| `Gemini` | Large-context reading, CJK/bilingual synthesis, second-opinion review | Bulk code generation |

If the task needs deep project memory, cross-conversation judgment, or nuanced tradeoffs, keep it in Claude.

## Required Output Contract

Every wrapper run must leave machine-readable status in:

`<log-file>.result.json`

Required fields:

```json
{
  "status": "success|fallback|error",
  "delegate": "codex",
  "model": "codex/<model>",
  "log_file": "<path>",
  "output_file": "<path or empty>",
  "summary": "",
  "risks": [],
  "files_changed": [],
  "tests_run": [],
  "timestamp_utc": "2026-04-24T00:00:00Z"
}
```

The wrappers only guarantee the contract exists. Claude must still inspect the diff and fill in any real acceptance judgment from the actual changes.

## Supervisor Workflow

### 1. Write a task file

For any non-trivial task, create `.ai/codex_task_<name>.md`:

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

### 2. Launch Codex synchronously

From Claude Code Bash:

```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." \
  --log-file .ai/codex_log_<name>.txt
```

PowerShell direct call is also supported:

```powershell
& "C:\Users\wenyu\mispricing-engine\.claude\skills\codex-delegate\scripts\run_codex.ps1" `
    -Prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." `
    -LogFile "C:\Users\wenyu\mispricing-engine\.ai\codex_log_<name>.txt"
```

Do not wrap these in `Start-Process`. Call them inline so file writes persist.

### 3. Check wrapper status first

```bash
cat .ai/codex_log_<name>.txt.result.json
```

If status is `fallback`, Codex quota was hit and Claude must do the work directly.

### 4. Claude acceptance gate

Claude must do all of the following before claiming success:

- Read the changed files or diff
- Confirm the change stayed inside scope
- Run the required verification commands
- Reject the result if Codex drifted from the brief

Passing wrapper execution is not acceptance. It only proves the delegate run finished.

## Good Delegation Targets

- Refactor a repeated pattern across 10+ files
- Generate unit tests from a clear implementation
- Add logging, docstrings, or type hints at scale
- Rename imports, constants, or terminology across a codebase
- Produce deterministic scaffolding from a precise spec

## Bad Delegation Targets

- Diagnose an intermittent production bug
- Decide between competing architectures
- Review auth, secrets, validation, or permission logic
- Resolve unclear requirements through conversation
- Make claims that need human defensibility or project memory

## Windows Runner Note

Keep platform quirks in the runner scripts, not in the task brief.

- Claude Code Bash uses Unix shell syntax on Windows
- Use forward slashes in bash examples
- Use PowerShell examples only when calling `.ps1` directly
- Never use `Start-Process` for these wrappers from Claude Code sessions

## Wrapper Behavior

Both wrappers:

- run synchronously
- detect quota/rate-limit failures
- write `.fallback_claude`, `.done`, `.error` sentinels
- emit `<log>.result.json`

Use `CODEX_PATH` when you need to override the Codex executable for testing or custom environments.

## Minimal Review Checklist

Before accepting delegate output:

- Was the task file specific enough?
- Did Codex stay inside the allowed write scope?
- Does the diff match the requested intent?
- Did required tests actually run?
- Are risks or follow-ups obvious from the changes?

If any answer is no, fix the task file or take the rest locally in Claude.
