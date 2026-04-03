# codex-delegate — Claude Code Skill

Delegate token-heavy coding tasks from Claude Code (or Cowork) to **Codex CLI** (OpenAI) or **Gemini CLI**, saving Claude tokens for planning, evaluation, and review.

---

## What it does

When Claude encounters a task requiring 100+ lines of code — batch file edits, test generation, boilerplate, migrations — it writes a structured context file and hands off execution to Codex CLI. Claude then reviews the output and fixes the remaining 10–20%.

**Result:** Claude spends tokens on judgment, not bulk generation. Tasks that would exhaust a context window finish in the background while Claude moves on.

---

## Prerequisites

### Required
- **Codex CLI** (OpenAI):
  ```bash
  npm i -g @openai/codex
  codex --version   # verify
  ```
  Requires an OpenAI API key (`OPENAI_API_KEY` env var).

### Optional
- **Gemini CLI** (for CJK/Chinese content and large-context tasks):
  ```bash
  npm i -g @google/gemini-cli
  gemini --version  # verify
  ```
  Requires a Google AI API key (`GEMINI_API_KEY` env var).

---

## Installation

### Claude Code

1. Copy the skill into your project's `.claude/skills/` directory:
   ```bash
   mkdir -p .claude/skills/codex-delegate
   cp path/to/codex-delegate/SKILL.md .claude/skills/codex-delegate/
   cp path/to/codex-delegate/scripts/ .claude/skills/codex-delegate/scripts/ -r
   ```

2. Add delegation rules to your project's `CLAUDE.md` (see [CLAUDE.md Setup](#claudemd-setup) below).

### Cowork

1. Place the skill files anywhere accessible to your Cowork workspace.
2. Reference `SKILL.md` in your Cowork system prompt or project instructions.
3. Use `run_codex.ps1` (Windows) or `run_codex.sh` (Mac/Linux) as the execution helper.

---

## CLAUDE.md Setup

Add these rules to your project's `CLAUDE.md` so delegation happens automatically:

```markdown
## Delegation Rules (IMPORTANT)
- Read `.claude/skills/codex-delegate/SKILL.md` before any task with 100+ lines of code changes.
- Token-heavy Python/backend work (tests, boilerplate, batch edits, migrations) → delegate to Codex CLI
- Chinese/CJK content (reports, comments, translated docs) → auto-routes to Gemini CLI
- Architecture decisions, bug diagnosis, security, multi-subsystem coupling → keep in Claude
- Claude's role: plan → write context file → launch Codex/Gemini → review output → fix remaining issues
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

## Usage Scenarios

### Claude Code: direct `codex exec` in Bash

Claude writes a context file, then calls Codex directly:

```bash
# Claude writes .ai/codex_task_tests.md with full context
# Then launches Codex:
codex exec --full-auto -C /path/to/repo -m gpt-5.4 \
  "Read .ai/codex_task_tests.md and execute all instructions."

# Check result
git diff
```

For parallel independent tasks (e.g. two unrelated modules):
```bash
codex exec --full-auto -C /repo "Read .ai/task_a.md and execute." &
codex exec --full-auto -C /repo "Read .ai/task_b.md and execute." &
wait
```

### Cowork (Windows): via PowerShell MCP

**Read-only analysis (most reliable from Cowork):**
```powershell
$script = "C:\path\to\codex-delegate\scripts\run_codex.ps1"
Start-Process powershell -ArgumentList `
  "-ExecutionPolicy Bypass -File `"$script`" -Prompt `"Read .ai/codex_task_foo.md and analyze.`" -LogFile `"$REPO\.ai\log_foo.txt`"" `
  -WindowStyle Hidden

# Poll for completion
while (!(Test-Path "$REPO\.ai\log_foo.txt.done")) { Start-Sleep 10 }
Get-Content "$REPO\.ai\log_foo.txt"
```

**File modifications (recommended: delegate to a Claude Code task):**
```
start_code_task: "Run codex exec --full-auto -C . -m gpt-5.4
  'Read .ai/codex_task_foo.md and execute.' then verify with git diff and commit."
```

> **Why the indirection?** Codex's `--full-auto` sandbox only persists writes when called from inside an active Claude Code session, not from external PowerShell. Delegating to `start_code_task` gives Codex proper filesystem access.

### Scheduled tasks / automation

Embed Codex calls in cron jobs or CI pipelines:
```bash
# In a scheduled shell script:
cd /repo
codex exec --full-auto -C . -m gpt-5.4 \
  "Read .ai/codex_task_weekly_report.md and execute." \
  -o .ai/codex_result_report.md
```

---

## Core Workflow: Context File Pattern

For any non-trivial task, write a context file first. This is better than inline prompts: reusable, version-controlled, no length limits.

### Step 1 — Claude writes the context file

Save to `.ai/codex_task_<name>.md` (gitignored by default):

```markdown
# Task: <descriptive name>

## Context
- Repo root: (Codex reads from its working directory -C flag)
- Key files to read: src/module_a.py, src/module_b.py
- Key files to modify: tests/test_module_a.py

## Instructions
1. Read the implementation in src/module_a.py
2. Generate pytest unit tests covering all public functions
3. Use existing test style from tests/test_existing.py as reference
4. Add fixtures for common setup

## Constraints
- Do not modify files outside the listed paths
- Follow existing code style (tabs vs spaces, naming conventions)
- Each test function must have a docstring

## Output
- Write tests to tests/test_module_a.py
- Write a summary of what was generated to .ai/codex_result_tests.md
```

### Step 2 — Launch Codex

```bash
codex exec --full-auto -C /repo -m gpt-5.4 \
  "Read .ai/codex_task_tests.md and execute all instructions inside."
```

### Step 3 — Claude reviews

- Read the modified files
- Run tests to verify they pass
- If 80%+ correct: fix remaining issues directly
- If fundamentally wrong: update context file and re-run

---

## CJK / Chinese Auto-routing

`run_codex.ps1` (and `run_codex.sh`) **auto-detect CJK characters** in the prompt and silently reroute to Gemini CLI. This avoids a known issue where Codex CLI on Windows silently truncates or garbles non-ASCII shell arguments.

You can also force Gemini explicitly:
```powershell
# PowerShell
.\run_codex.ps1 -Prompt "生成分析報告" -UseGemini -LogFile ".ai\log.txt"
```
```bash
# Bash
./run_codex.sh --prompt "生成分析報告" --use-gemini --log-file ".ai/log.txt"
```

---

## Key Flags Reference

| Flag | Purpose |
|------|---------|
| `--full-auto` | Auto-approve all tool calls + workspace write sandbox |
| `-C <dir>` | Set working directory for Codex |
| `-m <model>` | Model (default: `gpt-5.4`, or set `CODEX_MODEL` env var) |
| `-o <file>` | Write last message to file |
| `--json` | JSONL event stream for programmatic control |
| `--output-schema <file>` | Force structured JSON output |

---

## Important Caveats

- **Codex has no persistent memory** — always give full context via file paths in the context file, never assume it knows prior decisions
- **Codex cannot read conversation history** — summarize all relevant decisions in the context file
- **Sandbox limitation** — Codex can only write to the workspace dir (`-C`) and `/tmp`
- **Always verify output** before committing — run tests, check diffs, spot-check numbers
- **Windows encoding** — do not pass CJK text inline; use the helper script which writes prompt to a UTF-8 temp file first
- **`.ai/` is gitignored** — safe place for task files, logs, and intermediate outputs

---

## File Structure

```
codex-delegate/
├── README.md                          # This file
├── SKILL.md                           # Skill definition (loaded by Claude Code)
├── scripts/
│   ├── run_codex.ps1                  # PowerShell wrapper (Windows / Cowork)
│   └── run_codex.sh                   # Bash wrapper (Mac / Linux)
└── examples/
    ├── example_context_file.md        # Template for .ai/codex_task_*.md
    └── example_claude_md_rules.md     # Copy-paste CLAUDE.md delegation rules
```

---

## License

MIT
