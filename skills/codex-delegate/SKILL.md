---
name: codex-delegate
description: Delegates implementation-heavy or repetitive coding work (batch edits, boilerplate, multi-file refactors with clear patterns, test scaffolding) from Claude to OpenAI Codex CLI. Use when token cost outweighs judgment cost. Trigger phrases include "delegate to codex", "let codex do this", "batch refactor across files", "scaffold tests for". Avoid for architecture, security review, or root-cause debugging.
license: MIT
---

# Codex Delegate Skill

Claude is the supervisor. Codex CLI runs the mechanical work. Claude plans, constrains scope, reviews the diff, and verifies outcomes.

## Hard rules

- Before invoking the wrapper, run `codex --version` via Bash. If it fails, stop and tell the user to `npm install -g @openai/codex`.
- When calling `codex exec` directly (not through the wrapper), close stdin explicitly (`</dev/null`); the wrapper handles this internally.
- Wrapper run leaves machine-readable status at `<log-file>.result.json`. Acceptance is Claude's job, not the wrapper's.
- Do not wrap the wrapper in `Start-Process`. Call it inline so file writes persist.

## When to delegate

Mechanical → `codex` · Reasoning → `claude` · Long-context synthesis → `gemini`.

Full routing table and good/bad examples: `references/delegation-targets.md`.

## Workflow

1. **Brief**: write `.ai/codex_task_<name>.md` with Context / Goal / Constraints / Acceptance. Template: `references/task-template.md`. If the brief was already written by `agent-task-splitter` at `.ai/codex_task_<NNN>_<slug>.md`, read `.coord/plan.yml` for round context first.

2. **Run**: from Claude Code Bash, invoke the wrapper from its install location (user-scope skills install at `~/.claude/skills/`):
   ```bash
   bash ~/.claude/skills/codex-delegate/scripts/run_codex.sh \
     --prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." \
     --repo "$PWD" \
     --log-file .ai/codex_log_<name>.txt
   ```
   `--repo "$PWD"` overrides the wrapper default so it operates on the current project. PowerShell variant + env vars: `references/wrapper.md`.

3. **Read status**: `cat .ai/codex_log_<name>.txt.result.json`.
   - `success` → diff still needs review.
   - `fallback` → Codex quota hit; Claude must take over.
   - `error` → wrapper failed; check `<log>.error`.

4. **Accept**: read the diff, confirm scope, run the verification commands listed in the task file. Reject if Codex drifted. Extended checklist: `references/review-checklist.md`.

## Output contract

`.result.json` includes at minimum: `status` (success|fallback|error), `delegate` ("codex"), `model`, `log_file`, `output_file`, `summary`, `risks`, `files_changed`, `tests_run`, `timestamp_utc`. Full schema and status semantics: `references/output-contract.md`.

## Compatibility

- Tested with `@openai/codex` 0.128.0 (May 2026). Should work with any version that accepts `codex exec --sandbox workspace-write`.
- Default model: `gpt-5.4` (override via `--model` or `-Model`). Other models on your CLI: see `codex models`.
- Wrapper calls `codex exec --sandbox workspace-write -C <repo> -m <model>`. The older `--full-auto` flag is deprecated in 0.128+ and was replaced.
- `codex exec` runs in non-interactive mode and auto-approves (no `--ask-for-approval` flag exists on `exec`; that flag is top-level only).
- Direct `codex exec` calls must close stdin (`</dev/null`) to avoid the historical hang (issue #20919).
- PowerShell wrapper requires `$ErrorActionPreference` to NOT be `Stop` so stderr writes (warnings, banners) don't trip the catch block.

## See also

- `references/delegation-targets.md` — when to use vs avoid
- `references/wrapper.md` — full wrapper invocation, env vars, Windows runner notes
- `references/task-template.md` — task brief template
- `references/output-contract.md` — full `.result.json` schema, status semantics, `.fallback_claude` quota sentinel
- `references/review-checklist.md` — extended acceptance gate
- `references/patterns.md` — five single-task delegation shapes (context file, parallel, resume, structured output, review mode)
- `references/multi-agent.md` — leaf role in router/leaves architecture; when to route through `research-hub-multi-ai` or `agent-task-splitter`
- `references/examples.md` — concrete invocation examples on `codex-cli` 0.128.0+ syntax
