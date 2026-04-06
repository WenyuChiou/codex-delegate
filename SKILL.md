---
name: codex-delegate
description: "Delegate coding tasks to OpenAI Codex CLI (GPT-5.4 coding agent). Use this skill whenever Claude needs to offload code generation, file editing, code review, or any Python/backend task involving 100+ lines of changes. Triggers: 'use codex', 'delegate to codex', 'codex cli', large refactors, test generation, boilerplate code, batch file edits, migrations, or when CLAUDE.md delegation rules say to route work to Codex."
---

# Codex CLI Delegation

Codex CLI is OpenAI's coding agent (GPT-5.4), installed locally via npm. Use it as a worker: Claude plans, writes context, launches Codex, and reviews output.

## When to Delegate

- **Python/backend code**: 100+ lines of new code, boilerplate, migrations
- **Test generation**: unit tests, integration tests, test fixtures
- **Multi-file refactors**: renaming, pattern extraction, constant consolidation
- **Code review**: `codex exec review` for automated review
- **Batch edits**: repetitive changes across many files

Keep in Claude: architecture decisions, security review, multi-subsystem debugging, CJK content (use Gemini instead).

## Invocation Syntax (Windows — CRITICAL)

Codex CLI must be invoked via **cmd shell** with `cd /d` to set the workspace:

```bash
# Pattern 1: Echo prompt (short tasks)
cd /d C:\Users\wenyu\project && echo your prompt here | codex exec --full-auto

# Pattern 2: Pipe context file (complex tasks — PREFERRED)
cd /d C:\Users\wenyu\project && type task.md | codex exec --full-auto

# Pattern 3: Code review
cd /d C:\Users\wenyu\project && codex exec review --full-auto
```

**Key rules:**
- Always use `shell: "cmd"` in Desktop Commander
- Always `cd /d <project-dir>` first — this sets the sandbox workspace correctly
- Always use `--full-auto` (enables workspace-write sandbox + auto-approval)
- Pipe prompt via stdin: `echo ... | codex exec --full-auto` or `type file.md | codex exec --full-auto`
- Set `timeout_ms: 120000`+ for complex tasks (Codex can take 30-120s)
- **Writes persist** when invoked this way (confirmed 2026-04-06)

**DO NOT:**
- Use `cmd /c` wrapper in PowerShell scripts (writes don't persist through this wrapper)
- Use `-f` flag (doesn't exist)
- Use `-p` flag (doesn't exist — prompt is positional or via stdin)

## Delegation Workflow

### Step 1: Write a Context File

```markdown
# Task: [clear title]

## Goal
[What to produce]

## Files to Modify
- `path/to/file.py` — what to change and why

## Requirements
- [Specific requirements]
- [Edge cases to handle]
```

### Step 2: Launch Codex

```bash
cd /d C:\Users\wenyu\mispricing-engine && type task.md | codex exec --full-auto
```

### Step 3: Review Output

1. Check files were actually modified on disk
2. Run tests / linters
3. Fix remaining issues Claude-side

## Codex CLI Options Reference

| Option | Purpose |
|--------|---------|
| `--full-auto` | workspace-write sandbox + auto-approval (default for delegation) |
| `-C <dir>` | Set working directory (alternative to `cd /d`) |
| `-m <model>` | Override model (default: gpt-5.4) |
| `--sandbox workspace-write` | Allow writes to workspace only |
| `--sandbox danger-full-access` | Full disk access (use sparingly) |
| `--add-dir <dir>` | Allow additional writable directories |
| `--ephemeral` | Don't persist session files |
| `-o <file>` | Save last message to file |
| `--json` | Output events as JSONL |
| `exec review` | Run automated code review |

## Known Limitations

1. **No shared context**: Codex can't see Claude's conversation — always write a complete context file
2. **Sandbox scope**: `--full-auto` only allows writes within the workspace directory (set by `cd /d`)
3. **PowerShell wrapper breaks writes**: Never invoke via `cmd /c` in PS scripts — use cmd shell directly
4. **Single process**: Don't run multiple Codex processes simultaneously
5. **No Chinese/CJK**: Codex doesn't handle CJK content well — use Gemini CLI instead

## Task Routing: Codex vs Gemini

```
Python/backend code generation?     -> Codex
Code review?                        -> Codex
Test generation?                    -> Codex
Chinese/CJK content?                -> Gemini
JS/React/frontend?                  -> Gemini
Bilingual documentation?            -> Gemini
Architecture / security review?     -> Keep in Claude
```

## Examples

See `references/examples.md` for complete delegation examples.
