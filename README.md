# codex-delegate — Claude Code Skill

Delegate token-heavy coding tasks from Claude Code to **Codex CLI** (OpenAI), saving Claude tokens for planning, evaluation, and review.

---

## What it does

When Claude encounters a task requiring 100+ lines of code — batch file edits, test generation, boilerplate, migrations — it writes a structured context file and hands off execution to Codex CLI. Claude then reviews the output and fixes the remaining 10–20%.

If Codex hits a quota or rate limit, the helper script automatically creates a `.fallback_claude` sentinel file so Claude knows to handle the task itself.

**Result:** Claude spends tokens on judgment, not bulk generation. Tasks that would exhaust a context window finish quickly while Claude moves on.

---

## Prerequisites

- **Codex CLI** (OpenAI):
  ```bash
  npm i -g @openai/codex
  codex --version   # verify
  ```
  Requires an OpenAI API key (`OPENAI_API_KEY` env var).

> **Note on Gemini:** Previous versions of this skill included Gemini CLI as a fallback provider and for CJK/Chinese content routing. This version uses **Codex only**. If Codex quota is exceeded, the script signals Claude to handle the task directly (see [Quota Fallback](#quota-fallback)). For CJK content, invoke Gemini manually if needed.

---

## Installation

### Claude Code

1. Copy the skill into your project's `.claude/skills/` directory:
   ```bash
   mkdir -p .claude/skills/codex-delegate/scripts
   cp path/to/codex-delegate/SKILL.md .claude/skills/codex-delegate/
   cp path/to/codex-delegate/scripts/run_codex.ps1 .claude/skills/codex-delegate/scripts/
   cp path/to/codex-delegate/scripts/run_codex.sh  .claude/skills/codex-delegate/scripts/
   chmod +x .claude/skills/codex-delegate/scripts/run_codex.sh
   ```

2. Add delegation rules to your project's `CLAUDE.md` (see [CLAUDE.md Setup](#claudemd-setup) below).

---

## CLAUDE.md Setup

Add these rules to your project's `CLAUDE.md` so delegation happens automatically:

```markdown
## Delegation Rules (IMPORTANT)
- Read `.claude/skills/codex-delegate/SKILL.md` before any task with 100+ lines of code changes.
- Token-heavy Python/backend work (tests, boilerplate, batch edits, migrations) → delegate to Codex CLI
- Architecture decisions, bug diagnosis, security, multi-subsystem coupling → keep in Claude
- Claude's role: plan → write context file → launch Codex → review output → fix remaining issues
- If `.fallback_claude` sentinel appears after launching Codex, do the task yourself immediately
```

---

## When to Delegate vs Keep in Claude

### Delegate to Codex
| Task | Why Codex |
|------|-----------|
| Batch file edits (terminology, imports, paths) | Mechanical, pattern-based |
| Test scaffold generation | Boilerplate from existing impl |
| Code migration (10+ files, clear pattern) | Repetitive application of a rule |
| Adding type hints / docstrings / logging en masse | Formulaic |
| Data pipeline scripts (read → transform → output) | Spec-driven writing |
| Translation tasks with consistent terminology | Bulk text work |
| Writing docs or README sections from structured data | Token-heavy prose generation |

### Keep in Claude
| Task | Why Claude |
|------|-----------|
| Architecture decisions, API contracts | Needs project memory and judgment |
| Bug diagnosis with complex state | Claude traces context; Codex only sees what you tell it |
| Code touching multiple subsystems with implicit coupling | Risk of subtle breakage |
| Security-sensitive code (auth, input validation) | Needs careful review, not bulk generation |
| Tasks requiring iterative dialogue | Codex has no conversation history |
| Nuanced judgment calls | What's defensible, what's correct |

---

## Usage

### Claude Code: synchronous execution (RECOMMENDED)

Call the helper script **directly** from Bash — never via `Start-Process`. Direct invocation is the only reliable way to ensure Codex file writes persist from within a Claude Code session.

```bash
# Write a context file first (see Core Workflow below)
# Then launch Codex synchronously:
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_tests.md and execute all instructions." \
  --log-file .ai/codex_log_tests.txt

# Check for quota fallback sentinel
if [ -f ".ai/codex_log_tests.txt.fallback_claude" ]; then
    echo "Codex quota exceeded — handling task directly"
    # Do the work yourself here
elif [ -f ".ai/codex_log_tests.txt.done" ]; then
    cat ".ai/codex_log_tests.txt"
fi
```

PowerShell equivalent (call ps1 directly — no `Start-Process` wrapper):
```powershell
& ".claude\skills\codex-delegate\scripts\run_codex.ps1" `
    -Prompt "Read .ai/codex_task_tests.md and execute all instructions." `
    -LogFile ".ai\codex_log_tests.txt"

if (Test-Path ".ai\codex_log_tests.txt.fallback_claude") {
    Write-Host "Codex quota exceeded — handling task directly"
} elseif (Test-Path ".ai\codex_log_tests.txt.done") {
    Get-Content ".ai\codex_log_tests.txt"
}
```

### Direct `codex exec` (short tasks)
For short, focused tasks where you don't need file-based signaling:
```bash
codex exec --full-auto -C /path/to/repo -m gpt-5.4 \
  "Read .ai/codex_task_tests.md and execute all instructions."
git diff
```

---

## Quota Fallback

The helper scripts automatically detect Codex API quota exhaustion and signal Claude to handle the task itself.

### Fallback chain
```
Codex CLI → .fallback_claude sentinel (Claude handles it)
```

### Detection patterns
The scripts check for:
- Exit code `429`
- Output/stderr containing: `"quota exceeded"`, `"rate limit"`, `"insufficient_quota"`, `"too many requests"`, `"RateLimitError"`, `"429"`

### Sentinel files written on quota error
| File | Content | Meaning |
|------|---------|---------|
| `<log>.error` | `ALL_QUOTA_EXCEEDED\|<timestamp>` | Quota was the failure cause |
| `<log>.fallback_claude` | `FALLBACK_TO_CLAUDE\|<timestamp>` | Claude should do the task |
| `<log>.done` | `FALLBACK\|<timestamp>` | Signals completion to any polling loop |

### Output tagging
On success, the log file begins with `[MODEL_USED: codex/<model>]`.
On quota fallback, the log begins with `[CODEX QUOTA EXCEEDED at <timestamp>]`.

---

## Core Workflow: Context File Pattern

For any non-trivial task, write a context file first. This is better than inline prompts: reusable, version-controlled, no length limits.

### Step 1 — Claude writes the context file

Save to `.ai/codex_task_<name>.md` (gitignored by default):

```markdown
# Task: <descriptive name>

## Context
- Key files to read: src/module_a.py, src/module_b.py
- Key files to modify: tests/test_module_a.py

## Instructions
1. Read the implementation in src/module_a.py
2. Generate pytest unit tests covering all public functions
3. Use existing test style from tests/test_existing.py as reference

## Constraints
- Do not modify files outside the listed paths
- Follow existing code style exactly

## Output
- Write tests to tests/test_module_a.py
- Write a summary to .ai/codex_result_tests.md
```

### Step 2 — Launch Codex via helper script
```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_tests.md and execute all instructions." \
  --log-file .ai/codex_log_tests.txt
```

### Step 3 — Check for fallback, then review
```bash
if [ -f ".ai/codex_log_tests.txt.fallback_claude" ]; then
    echo "Quota exceeded — doing task myself"
elif [ -f ".ai/codex_log_tests.txt.done" ]; then
    python -m pytest tests/test_module_a.py -v
    git diff
fi
```

---

## Parallel Execution
```bash
# Launch both tasks; first runs in background
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/task_a.md and execute." \
  --log-file .ai/log_a.txt &

bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/task_b.md and execute." \
  --log-file .ai/log_b.txt

wait

# Check results
for log in .ai/log_a.txt .ai/log_b.txt; do
    if [ -f "${log}.fallback_claude" ]; then
        echo "$log: quota exceeded — Claude should handle"
    else
        echo "$log: $(head -1 "$log")"
    fi
done
```

---

## Script Parameters

### run_codex.sh
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prompt` | (required) | Task prompt |
| `--repo` | `~/mispricing-engine` | Working directory |
| `--model` | `gpt-5.4` | Codex model |
| `--output-file` | (none) | Codex `-o` file |
| `--log-file` | `<repo>/.ai/codex_output.txt` | Log file path |
| `--synchronous` | (flag, always on) | Documents synchronous intent |

### run_codex.ps1
| Parameter | Default | Description |
|-----------|---------|-------------|
| `-Prompt` | (required) | Task prompt |
| `-Repo` | `C:\Users\wenyu\mispricing-engine` | Working directory |
| `-Model` | `gpt-5.4` | Codex model |
| `-OutputFile` | (none) | Codex `-o` file |
| `-LogFile` | `<Repo>\.ai\codex_output.txt` | Log file path |
| `-Synchronous` | `$true` | Run inline (always pass `$true` from Claude Code) |

## Codex Key Flags Reference

| Flag | Purpose |
|------|---------|
| `--full-auto` | Auto-approve all tool calls + workspace write sandbox |
| `-C <dir>` | Set working directory for Codex |
| `-m <model>` | Model (default: `gpt-5.4`) |
| `-o <file>` | Write last message to file |
| `--json` | JSONL event stream for programmatic control |
| `--output-schema <file>` | Force structured JSON output |

---

## Important Caveats

- **Codex has no persistent memory** — always give full context via file paths in the context file
- **Codex cannot read conversation history** — summarize all relevant decisions in the context file
- **Sandbox limitation** — Codex can only write to the workspace dir (`-C`) and `/tmp`
- **Always verify output** before committing — run tests, check diffs, spot-check numbers
- **Never use `Start-Process`** to launch this script from a Claude Code session — file writes won't persist; call the script directly
- **`.ai/` is gitignored** — safe place for task files, logs, and intermediate outputs
- **If `.fallback_claude` appears** after launching, do the task yourself immediately

---

## File Structure

```
codex-delegate/
├── README.md                          # This file
├── SKILL.md                           # Skill definition (loaded by Claude Code)
├── scripts/
│   ├── run_codex.ps1                  # PowerShell wrapper (Windows)
│   └── run_codex.sh                   # Bash wrapper (Mac / Linux)
└── examples/
    ├── example_context_file.md        # Template for .ai/codex_task_*.md
    └── example_claude_md_rules.md     # Copy-paste CLAUDE.md delegation rules
```

---

## License

MIT
