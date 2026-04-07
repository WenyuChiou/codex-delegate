---
name: codex-delegate
description: "Delegate token-heavy coding tasks to Codex CLI (OpenAI gpt-5.4) from Claude Code. Use this skill whenever you need to write large amounts of code, do batch file edits, generate boilerplate, write tests, migrate code patterns, or do any token-heavy execution work. ALWAYS use this skill instead of writing 100+ lines of code yourself. This skill saves Claude tokens by routing bulk work to cheaper models while Claude focuses on planning, evaluation, and review."
---

# Codex Delegate Skill

You are Claude acting as a **supervisor**. You plan, evaluate, and review. Codex does the heavy writing.

## Important: Execution Environment

### Synchronous Execution (Claude Code sessions — RECOMMENDED)
From a Claude Code session, call the helper script **directly** in Bash. This is the only reliable way to ensure file writes persist:

```bash
# Direct synchronous call — file writes always persist
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_foo.md and execute all instructions." \
  --log-file .ai/codex_log_foo.txt
```

Or call the PowerShell script directly (no Start-Process wrapper):
```powershell
# From Claude Code Bash tool — call ps1 directly, NOT via Start-Process
& "C:\Users\wenyu\mispricing-engine\.claude\skills\codex-delegate\scripts\run_codex.ps1" `
    -Prompt "Read .ai/codex_task_foo.md and execute all instructions." `
    -LogFile "C:\Users\wenyu\mispricing-engine\.ai\codex_log_foo.txt"
```

### Why NOT Start-Process
`Start-Process powershell -ArgumentList "-File run_codex.ps1 ..."` is **flaky from Claude Code sessions** — Codex runs in a write-sandbox where file modifications may not persist on disk even when the output log shows correct diffs. Always call the script directly (synchronous) instead.

## Quota Fallback

The helper scripts implement automatic fallback when Codex API quotas are exhausted.

### Fallback Chain
```
Codex CLI → .fallback_claude sentinel (Claude does the task itself)
```

### How it works
1. Script runs Codex CLI normally.
2. If exit code is 429 **or** stderr/stdout contains quota patterns (`"quota exceeded"`, `"rate limit"`, `"insufficient_quota"`, `"too many requests"`, etc.) → quota detected.
3. Script writes two files:
   - `<log>.error` — contains `ALL_QUOTA_EXCEEDED|<timestamp>`
   - `<log>.fallback_claude` — sentinel file (`FALLBACK_TO_CLAUDE|<timestamp>`)
   - `<log>.done` — contains `FALLBACK|<timestamp>` (signals completion to polling loop)
4. **After polling for `.done`**, check for `.fallback_claude`. If it exists, **do the task yourself** instead of retrying Codex.

### Claude: check for fallback sentinel
```bash
# After polling for done:
if [ -f ".ai/codex_log_foo.txt.fallback_claude" ]; then
    echo "Codex quota exceeded — handling task directly"
    # Do the task yourself here
fi
```

```powershell
# PowerShell equivalent:
if (Test-Path ".ai\codex_log_foo.txt.fallback_claude") {
    Write-Host "Codex quota exceeded — handling task directly"
    # Do the task yourself here
}
```

### Output tagging
On success, the log file begins with `[MODEL_USED: codex/<model>]` so you know which model ran.
On quota fallback, the log begins with `[CODEX QUOTA EXCEEDED at <timestamp>]`.

### Note on Gemini
Gemini CLI (`gemini`) was previously used for CJK/Chinese content routing and as a quota fallback. **This skill does not include Gemini.** For CJK/Chinese content, use the separate `gemini-delegate` skill.

## Cross-Platform Note (Claude Code Bash = git-bash)

Claude Code's Bash tool runs **git-bash (Unix shell)** on Windows — NOT PowerShell or cmd.exe.

| Task | Claude Code Bash | ❌ Do NOT use (cmd.exe only) |
|------|-----------------|------------------------------|
| Read a file | `cat file.txt` | `type file.txt` |
| List files | `ls` | `dir` |
| Copy file | `cp src dst` | `copy src dst` |
| Delete file | `rm file` | `del file` |
| Create dir | `mkdir -p dir` | `md dir` |

All bash code blocks in this skill use Unix syntax and are intended for Claude Code's Bash tool. PowerShell examples are explicitly labeled with the `powershell` code fence and are for direct PowerShell invocation only.

## When to Delegate vs Keep

### Delegate to Codex (good for)
- Batch file edits across many files (terminology, paths, imports)
- Boilerplate generation (test scaffolds, config files, doc templates)
- Code migration / refactoring across 10+ files with clear patterns
- Writing analysis scripts from clear specs
- Adding type hints, docstrings, or logging en masse
- Generating unit tests from existing implementations
- Data pipeline scripts (read → transform → output)
- Translation tasks with consistent terminology
- Writing paper section drafts from structured data

### Keep in Claude (bad for Codex)
- Architecture decisions, API contract design, dependency choices
- Decisions requiring project history or memory context
- Nuanced judgment calls (what claims are defensible, circular reasoning)
- Bug diagnosis with complex state (Claude traces context better)
- Code touching multiple subsystems with implicit coupling
- Security-sensitive code (auth, input validation)
- Tasks requiring iterative dialogue with user
- Anything requiring verification against prior conversations

## Core Workflow: Context File Pattern (PREFERRED)

For any non-trivial task, write a structured context file first.

### Step 1: Claude writes the context file
Save to `.ai/codex_task_<name>.md` in the repo:

```markdown
# Task: <descriptive name>

## Context
- Repo: C:\Users\wenyu\mispricing-engine
- Key files to read: <list paths Codex should read>
- Key files to modify: <list paths Codex should write>

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

### Step 2: Launch Codex (synchronous, from Claude Code Bash)
```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." \
  --log-file .ai/codex_log_<name>.txt
```

### Step 3: Check result
```bash
# Check for fallback sentinel first
if [ -f ".ai/codex_log_<name>.txt.fallback_claude" ]; then
    echo "Quota exceeded — doing task myself"
elif [ -f ".ai/codex_log_<name>.txt.done" ]; then
    cat ".ai/codex_log_<name>.txt"
fi
```

### Step 4: Claude reviews
- Read the output/modified files
- Check against ground truth (run tests, verify numbers)
- If 80%+ correct: fix remaining issues directly
- If fundamentally wrong: rewrite context file and re-run

## Advanced Patterns

### Parallel Execution (from Claude Code Bash)
```bash
# Launch task A in background, run task B in foreground
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_a.md and execute." \
  --log-file .ai/log_a.txt &

bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_b.md and execute." \
  --log-file .ai/log_b.txt

wait  # wait for background task

# Check both results
for log in .ai/log_a.txt .ai/log_b.txt; do
    if [ -f "${log}.fallback_claude" ]; then
        echo "$log: quota exceeded — needs Claude"
    else
        echo "$log: $(head -1 $log)"
    fi
done
```

### Structured Output (for data extraction)
```bash
codex exec --full-auto --output-schema schema.json "Extract all benchmark numbers from the backtest results"
```
Forces JSON output matching schema. Good for pipeline tasks where Claude processes the result.

### Code Review Mode
```bash
codex exec review  # reviews current git diff
```

## Script Parameters

### run_codex.sh
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prompt` | (required) | Task prompt |
| `--repo` | `~/mispricing-engine` | Working directory |
| `--model` | `gpt-5.4` | Codex model |
| `--output-file` | (none) | Codex `-o` output file |
| `--log-file` | `<repo>/.ai/codex_output.txt` | Log file path |
| `--synchronous` | (flag, always on) | Documents synchronous intent |

### run_codex.ps1
| Parameter | Default | Description |
|-----------|---------|-------------|
| `-Prompt` | (required) | Task prompt |
| `-Repo` | `C:\Users\wenyu\mispricing-engine` | Working directory |
| `-Model` | `gpt-5.4` | Codex model |
| `-OutputFile` | (none) | Codex `-o` output file |
| `-LogFile` | `<Repo>\.ai\codex_output.txt` | Log file path |
| `-Synchronous` | `$true` | Run inline (not via Start-Process); always pass `$true` from Claude Code |

## Codex Key Flags Reference

| Flag | Purpose |
|------|---------|
| `--full-auto` | Auto-approve all tool calls + workspace write |
| `-C <dir>` | Set working directory |
| `-m <model>` | Model selection (default: gpt-5.4) |
| `-o <file>` | Write last message to file |
| `--json` | JSONL event stream for programmatic control |
| `--output-schema <file>` | Force structured JSON output |

## Important Caveats

- Codex has NO persistent memory — always give full context via file paths
- Codex cannot read conversation history — summarize decisions in the context file
- Sandbox: can only write to workspace dir and /tmp
- Always verify Codex output against ground truth before committing
- **Never** use `Start-Process` to launch this script from a Claude Code session — call it directly
- The `.ai/` directory is gitignored — safe for task files and logs
- If `.fallback_claude` sentinel appears after launch, do the task yourself immediately

