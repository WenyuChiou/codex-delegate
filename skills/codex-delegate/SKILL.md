---
name: codex-delegate
description: Delegates implementation-heavy or repetitive coding work (batch edits, boilerplate, multi-file refactors with clear patterns, test scaffolding) from Claude to OpenAI Codex CLI. Use when token cost outweighs judgment cost. Trigger phrases include "delegate to codex", "let codex do this", "batch refactor across files", "scaffold tests for". Avoid for architecture, security review, or root-cause debugging.
license: MIT
compatibility: Designed for Claude Code. Portable across agentskills.io-compliant hosts; the wrapper script lives at <skill-root>/scripts/run_codex.sh — adapt the example path to your host's skills directory (e.g. ~/.claude/skills/codex-delegate/ on Claude Code, ~/.hermes/skills/<category>/codex-delegate/ on Hermes).
---

# Codex Delegate Skill

Claude is the supervisor. Codex CLI runs the mechanical work. Claude plans, constrains scope, reviews the diff, and verifies outcomes.

## Why use this instead of raw `codex exec`

This wrapper is not cosmetic. It exists because every shipping task that bypasses it loses one of three things that have caused real incidents:

| What the wrapper handles | What raw `codex exec` costs you |
|---|---|
| **stdin closure** (`</dev/null`) | Codex hangs indefinitely (issue #20919). One session hit a 25-minute zero-byte hang on 2026-05-14 because the supervising agent forgot the redirect. |
| **`.result.json` structured contract** (`status` / `risks` / `files_changed` / `tests_run`) | You parse raw stdout. On a 10 MB log this is multi-thousand tokens of grep + interpretation per run. |
| **Brief template** (`references/task-template.md`) | Codex drifts. F11 (over-applied a sweep rule to the meta-doc documenting the rule) and F12 (injected unrequested "Attributions: Karpathy, Simon Willison, ..." lines) both shipped from no-brief raw invocations. |

### Measured token savings (real dogfood, not estimates)

From a 6-round mixed-workload session (`awesome-agentic-ai-zh` 2026-05-14, see `agent-collab-skills/docs/measured-benefits.md`):

| Workload | Saving vs Claude-inline | When it applies to you |
|---|---|---|
| **Mechanical sweep × 2 parallel** (e.g., term replacement, § strip, doc renumber) | **~7× token reduction** + caught 4 drift files | Repo with > 20 files needing the same edit |
| **Mirror sync** (zh-TW → zh-Hans + en, 8 files) | **17-22× token reduction** | Multi-locale docs / curricula |
| **Multi-file rename / typed-API migration** | ~3× (extrapolated from Phase D title-sweep) | > 10 files following one pattern |
| **Single-file < 50 line fix** | **~1× (don't bother)** | Use Claude direct Edit |
| **Architecture / debugging / security review** | **1× (skill cannot help)** | Claude direct |

The wrapper helps for **token-heavy mechanical work**. It does not help for judgment-heavy work — be honest about which one your task is.

### Anti-patterns this skill prevents

- **F11**: Codex over-applies a sweep rule to documentation describing that rule. Prevented by `agent-task-splitter` brief that explicitly lists in-scope files.
- **F14**: Operator (Claude) defaults to `Bash("codex exec ...")` despite the rule saying use `Skill("codex-delegate")`. Prevented by a `PreToolUse` hook on the operator side (template below).
- **Codex hang**: 25-minute zero-byte run on 2026-05-14 because raw `codex exec` was invoked without `</dev/null`. Prevented by wrapper's mandatory stdin closure.

### CLAUDE.md snippet to enforce routing

Drop this into your `~/.claude/CLAUDE.md` (or repo-level `CLAUDE.md`) to make the rule operational rather than aspirational:

```markdown
## Codex routing rule (enforced)

For any task that is mechanical, multi-file, has a clear pattern, or
batch-edits ≥ 5 files: invoke `Skill("codex-delegate", args="brief=...")`.
Do NOT use `Bash("codex exec ...")` for shipping tasks — it loses stdin
closure (codex hangs), the `.result.json` contract (no structured status),
and the brief template (Codex drifts F11/F12).

Optional mechanical enforcement: a PreToolUse hook on Bash that nudges raw
`codex exec` toward `Skill("codex-delegate")`. Reference implementation:
https://github.com/WenyuChiou/dotfiles-claude/blob/main/hooks/check_codex_skill_routing.py
```

→ The hook is non-blocking (warns only) so you can still run `codex --version` /
`codex exec resume` / `codex exec review` without friction. Replace `return 0`
with `return 2` in the hook to make it block instead of warn.

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

2. **Run**: from Claude Code Bash, invoke the wrapper from its install location:
   ```bash
   bash ~/.claude/skills/codex-delegate/scripts/run_codex.sh \
     --prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." \
     --repo "$PWD" \
     --log-file .ai/codex_log_<name>.txt
   ```
   `--repo` defaults to the caller's `$PWD`; pass `--repo "$PWD"` explicitly only if you want to be defensive about the working directory at invocation. On non-Claude-Code agentskills.io hosts, substitute the host's skills directory (e.g. `~/.hermes/skills/<category>/codex-delegate/scripts/run_codex.sh`). PowerShell variant + env vars: `references/wrapper.md`.

3. **Read status**: `cat .ai/codex_log_<name>.txt.result.json`.
   - `success` → diff still needs review.
   - `fallback` → Codex quota hit; Claude must take over.
   - `error` → wrapper failed; check `<log>.error`.

4. **Accept**: read the diff, confirm scope, run the verification commands listed in the task file. Reject if Codex drifted. Extended checklist: `references/review-checklist.md`.

## Output contract

`.result.json` includes at minimum: `status` (success|fallback|error), `delegate` ("codex"), `model`, `log_file`, `output_file`, `summary`, `risks`, `files_changed`, `tests_run`, `timestamp_utc`. Full schema and status semantics: `references/output-contract.md`.

## Compatibility

- Tested with `@openai/codex` 0.128.0 (May 2026). Should work with any version that accepts `codex exec --sandbox workspace-write`.
- Default model: `gpt-5.5` (bumped from `gpt-5.4` on 2026-05-14 per operator preference; override via `--model` or `-Model`). `gpt-5.4` remains available and is ~3× cheaper per token if cost-sensitive — trade-offs and an A/B-test recipe live in `references/model-selection.md`. Other models on your CLI: see `codex models`.
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
- `references/model-selection.md` — `gpt-5.4` vs `gpt-5.5` trade-offs (A/B-tested) + when to override the default
