---
name: codex-delegate
description: Use when a coding task is implementation-heavy, repetitive, or spans many files, and Claude should supervise while Codex CLI executes the mechanical work. Typical triggers include batch edits, boilerplate generation, large refactors with clear patterns, test scaffolding, and other token-heavy coding tasks. Do not use for architecture, root-cause debugging, security judgment, or ambiguous product decisions.
---

# Codex Delegate Skill

Claude is the supervisor. Claude plans, constrains scope, reviews the diff, and verifies outcomes. Codex is the execution specialist for implementation-heavy coding work.

## When to Use

Use this skill when the task is expensive in tokens but cheap in judgment.

| Route to | Best for | Avoid |
|----------|----------|-------|
| `Codex` | Multi-file implementation, boilerplate, test scaffolds, mechanical refactors, batch edits | Architecture, debugging root cause, security review |
| `Claude` | Requirements, design, API contracts, bug diagnosis, acceptance review | Large repetitive edits |
| `Gemini` | Large-context reading, CJK/bilingual synthesis, second-opinion review | Bulk code generation |

If the task needs deep project memory, cross-conversation judgment, or nuanced tradeoffs, keep it in Claude.

## Multi-Agent Coordination

This skill is the **leaf** in a router/leaves architecture:

- **Single delegate this round** (just Codex, just Gemini): use this skill directly.
- **Two or more delegates this round** (Codex + Gemini, multiple parallel Codex sessions, or a sequence of mixed handoffs): use the `research-hub-multi-ai` router first to write `.coord/multi_ai_plan.md`. Each leaf then reads its assigned task brief from that plan.

Do not hand-roll multi-agent coordination from inside this skill. The router owns task splitting, dependency ordering, and reconciliation.

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

## Five Workflow Patterns

Use this checklist when shaping a delegation. Each row tells you when the pattern fits and the mechanism.

| Pattern | When to reach for it | Mechanism |
|---|---|---|
| **Context file** | Brief is long, will be re-run, or spans multiple files | Write `.ai/codex_task_<name>.md`, point Codex at it from the wrapper |
| **Parallel execution** | Two or more independent subtasks on the same repo | Launch multiple wrapper runs in parallel from Claude Bash with `run_in_background=true`; give each a distinct log path |
| **Resume session** | Previous Codex output was 80% correct and you only need a fix-up | `codex exec resume --last` (or a specific session id) and ask Codex to address the specific issues |
| **Structured output** | Pipeline-style data extraction where Claude post-processes | `codex exec --full-auto --output-schema schema.json "..."` to force conformant JSON |
| **Review mode** | Quick second opinion on a staged diff | `codex exec review --full-auto` against the current working tree |

Ready-to-paste prompt templates for each pattern live in `references/patterns.md`.

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

- Claude Code Bash uses Unix shell syntax on Windows (git-bash). Do not use `cd /d` or other cmd.exe-only constructs in examples.
- Use forward slashes in bash examples
- Use PowerShell examples only when calling `.ps1` directly
- Never use `Start-Process` for these wrappers from Claude Code sessions

## Model Selection

Codex CLI's default model is `gpt-5.5`. With `codex-cli >= 0.121.0`, runs abort if that model is not available in your account. Set the model explicitly:

- Pass `-m gpt-5.4` (or another available model) on each call.
- Or set the default once in `~/.codex/config.toml`:

  ```toml
  [model]
  default = "gpt-5.4"
  ```

The shipped wrappers (`run_codex.sh`, `run_codex.ps1`) already default to `gpt-5.4`. This section only matters when you call `codex` directly, bypassing the wrapper.

If a run fails with a "model not available" or similar error, check this first.

## Non-Interactive Shell Note

Since `codex-cli >= 0.121.0`, non-interactive runs hang unless stdin is closed. Close stdin explicitly when calling `codex` directly:

```bash
codex exec --full-auto -C /repo "task" < /dev/null
```

```powershell
codex exec --full-auto -C C:\repo "task" *< $null
```

The wrappers handle this automatically. This section matters only for direct `codex` calls.

## Quota Fallback

When Codex hits its quota or rate limit, the wrappers write a `.fallback_claude` sentinel next to the log file and set `result.json` `status` to `fallback`. Claude must then:

1. Read the sentinel and `result.json` to confirm the fallback path.
2. Take the work directly in the current session, using the same task brief.
3. Not retry the Codex call — quota errors do not resolve quickly.

This avoids burning context on retry loops.

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
