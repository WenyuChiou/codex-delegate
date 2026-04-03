---
name: codex-delegate
description: "Delegate token-heavy coding tasks to Codex CLI (OpenAI) or Gemini CLI from Claude Code or Cowork. Use this skill whenever you need to write large amounts of code, do batch file edits, generate boilerplate, write tests, migrate code patterns, or do any token-heavy execution work. ALWAYS use this skill instead of writing 100+ lines of code yourself. This skill saves Claude tokens by routing bulk work to cheaper models while Claude focuses on planning, evaluation, and review."
---

# Codex/Gemini Delegate Skill

You are Claude acting as a **supervisor**. You plan, evaluate, and review. Codex and Gemini do the heavy writing.

## Important: Codex Sandbox Limitation

Codex CLI in `--full-auto` mode runs in a **write-sandbox**. When invoked via `cmd /c` or `Start-Process` (from Cowork), file modifications may NOT persist on disk even though the output log shows correct diffs.

**Recommended delegation patterns (in order of reliability):**
1. **Code review / read-only analysis** — Codex reads code and writes analysis to stdout → always works
2. **Claude Code session calls `codex exec` directly in Bash** → writes persist
3. **Diff generation** — Codex generates diffs, Claude applies them via Edit tool → reliable but manual
4. **From Cowork for file writes** — Use `start_code_task` to delegate to a Claude Code session that runs Codex internally

## When to Delegate vs Keep

### Delegate to Codex
- Batch file edits across many files (terminology, paths, imports)
- Boilerplate generation (test scaffolds, config files, doc templates)
- Code migration / refactoring across 10+ files with clear patterns
- Writing analysis scripts from clear specs
- Adding type hints, docstrings, or logging en masse
- Generating unit tests from existing implementations
- Data pipeline scripts (read → transform → output)
- Translation tasks with consistent terminology
- Writing section drafts from structured data

### Keep in Claude
- Architecture decisions, API contract design, dependency choices
- Decisions requiring project history or memory context
- Nuanced judgment calls
- Bug diagnosis with complex state (Claude traces context better)
- Code touching multiple subsystems with implicit coupling
- Security-sensitive code (auth, input validation)
- Tasks requiring iterative dialogue with user
- Anything requiring verification against prior conversations

## Execution Environment

### Environment Variables

Configure these to avoid hardcoding paths:

| Variable | Purpose | Default |
|----------|---------|---------|
| `REPO_ROOT` | Path to the repository root | Current working directory |
| `CODEX_PATH` | Path to Codex CLI executable | `codex` (assumes on PATH) |
| `GEMINI_PATH` | Path to Gemini CLI executable | `gemini` (assumes on PATH) |
| `CODEX_MODEL` | Default Codex model | `gpt-5.4` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `GEMINI_API_KEY` | Google AI API key | Required for Gemini |

### From Claude Code (Bash)

Call Codex directly:
```bash
REPO="${REPO_ROOT:-$(pwd)}"
MODEL="${CODEX_MODEL:-gpt-5.4}"
codex exec --full-auto -C "$REPO" -m "$MODEL" "Read .ai/codex_task_<name>.md and execute all instructions."
```

### From Cowork (via Windows PowerShell MCP)

**Critical: each PowerShell call is a NEW session** — variables and background jobs do NOT persist between calls. Use the helper script + file-based signaling.

**Method A: Read-only analysis / code review (MOST RELIABLE from Cowork)**
```powershell
$script  = "$env:SKILL_ROOT\scripts\run_codex.ps1"
$repo    = $env:REPO_ROOT
$logFile = "$repo\.ai\codex_log_foo.txt"

Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$script`" -Prompt `"Read .ai/codex_task_foo.md and execute all instructions.`" -Repo `"$repo`" -LogFile `"$logFile`"" -WindowStyle Hidden

# Poll for completion (every 30-60s)
while (!(Test-Path "$logFile.done")) { Start-Sleep 30 }
Get-Content $logFile
```

**Method B: File modifications via start_code_task (RELIABLE for writes)**
When Codex needs to modify files, delegate to a Claude Code task:
```
start_code_task: "Run codex exec --full-auto -C . -m gpt-5.4 'Read .ai/codex_task_foo.md and execute.' then verify changes with git diff and commit."
```

**Method C: Synchronous short tasks (<30s)**
```powershell
$repo = $env:REPO_ROOT
codex exec --full-auto -C "$repo" -m gpt-5.4 "short prompt here"
```

## Core Workflow: Context File Pattern (PREFERRED)

For any non-trivial task, write a structured context file first. This is better than long inline prompts: reusable, version-controlled, no length limits.

### Step 1: Claude writes the context file

Save to `.ai/codex_task_<name>.md` in the repo:

```markdown
# Task: <descriptive name>

## Context
- Repo root: (Codex reads from its working directory — set via -C flag)
- Key files to read: <list paths>
- Key files to modify: <list paths>

## Instructions
<Clear, step-by-step instructions. Include WHY not just WHAT.>

## Constraints
- Do not modify files outside the listed paths
- Follow existing code style (check adjacent files)
- Add docstrings to all public functions

## Output
- Save modified files in place
- Write a summary of changes to .ai/codex_result_<name>.md
```

### Step 2: Launch Codex

```bash
REPO="${REPO_ROOT:-$(pwd)}"
codex exec --full-auto -C "$REPO" -m "${CODEX_MODEL:-gpt-5.4}" \
  "Read .ai/codex_task_<name>.md and execute all instructions inside."
```

### Step 3: Claude reviews

- Read the output / modified files
- Check against ground truth (run tests, verify numbers)
- If 80%+ correct: fix remaining issues directly
- If fundamentally wrong: rewrite context file and re-run

## Advanced Patterns

### Parallel Execution

Launch multiple independent Codex tasks simultaneously:
```bash
# Bash (Mac/Linux/WSL)
REPO="${REPO_ROOT:-$(pwd)}"
codex exec --full-auto -C "$REPO" "Read .ai/task_a.md and execute." &
codex exec --full-auto -C "$REPO" "Read .ai/task_b.md and execute." &
wait
```

```powershell
# PowerShell (Windows)
$script = "$env:SKILL_ROOT\scripts\run_codex.ps1"
$repo   = $env:REPO_ROOT
Start-Process powershell -ArgumentList "-File `"$script`" -Prompt `"Read .ai/task_a.md and execute.`" -Repo `"$repo`" -LogFile `"$repo\.ai\log_a.txt`"" -WindowStyle Hidden
Start-Process powershell -ArgumentList "-File `"$script`" -Prompt `"Read .ai/task_b.md and execute.`" -Repo `"$repo`" -LogFile `"$repo\.ai\log_b.txt`"" -WindowStyle Hidden

# Poll for both
while (!((Test-Path "$repo\.ai\log_a.txt.done") -and (Test-Path "$repo\.ai\log_b.txt.done"))) { Start-Sleep 15 }
```

### Structured Output (for data extraction)

```bash
codex exec --full-auto --output-schema schema.json \
  "Extract all benchmark numbers from the backtest results"
```

Forces JSON output matching the schema. Good for pipeline tasks where Claude processes the result programmatically.

### Code Review Mode

```bash
codex exec review   # reviews current git diff
```

Quick second opinion on staged changes before committing.

## Gemini CLI

Best for:
- **Any task with Chinese/CJK content** — Codex CLI has argument encoding issues with CJK characters on Windows; Gemini handles them cleanly
- Research and web search tasks
- Long document summarization
- JS/React/frontend work
- Tasks where a larger context window helps

### Chinese/CJK encoding rule

The `run_codex.ps1` and `run_codex.sh` helpers **auto-detect CJK characters** in `$Prompt` and route to Gemini automatically. You can also pass `-UseGemini` / `--use-gemini` explicitly.

**Do NOT pass CJK text inline to `codex exec`** — argument parsing may silently truncate or garble the text on Windows. Always use the helper script, which writes the prompt to a UTF-8 temp file first.

## Key Flags Reference

| Flag | Purpose |
|------|---------|
| `--full-auto` | Auto-approve all tool calls + workspace write sandbox |
| `-C <dir>` | Set working directory |
| `-m <model>` | Model selection (default: `gpt-5.4`) |
| `-o <file>` | Write last message to file |
| `--json` | JSONL event stream for programmatic control |
| `--output-schema <file>` | Force structured JSON output |

## Important Caveats

- Codex has **no persistent memory** — always give full context via file paths in the context file
- Codex **cannot read conversation history** — summarize all relevant decisions in the context file
- Sandbox: can only write to workspace dir (`-C`) and `/tmp`
- **Always verify Codex output** against ground truth before committing
- The `.ai/` directory should be gitignored — safe for task files and logs
- Windows PowerShell sessions are stateless across calls — each call is a fresh shell
