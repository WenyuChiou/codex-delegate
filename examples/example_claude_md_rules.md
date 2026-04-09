# Example CLAUDE.md Delegation Rules

Copy the section below into your project's `CLAUDE.md` to enable automatic delegation.
Adjust the paths and examples to match your project's structure.

---

## Delegation Rules (IMPORTANT)

- **Read `.claude/skills/codex-delegate/SKILL.md` before any task with 100+ lines of code changes.**
- Token-heavy Python/backend work (tests, boilerplate, batch edits, migrations) → delegate to Codex CLI
- Architecture decisions, bug diagnosis, security, multi-subsystem coupling → keep in Claude
- Claude's role: **plan → write context file → launch Codex → review output → fix remaining issues**
- **If `.fallback_claude` sentinel appears after launching Codex, do the task yourself immediately**

### Decision Matrix

| Task | Where |
|------|-------|
| Write tests for an existing module | Codex |
| Batch rename a function across 15 files | Codex |
| Add type hints to an entire package | Codex |
| Generate a README from structured data | Codex |
| Migrate deprecated API calls across the codebase | Codex |
| Design a new module's API surface | Claude |
| Debug a subtle race condition | Claude |
| Write auth middleware | Claude |
| Refactor code that touches 3+ subsystems | Claude |

### Execution Pattern

**From Claude Code (bash) — synchronous, direct invocation:**
```bash
# 1. Write context file to .ai/codex_task_<name>.md
# 2. Launch Codex via helper script (NOT via Start-Process)
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_<name>.md and execute all instructions." \
  --log-file .ai/codex_log_<name>.txt

# 3. Check for quota fallback
if [ -f ".ai/codex_log_<name>.txt.fallback_claude" ]; then
    echo "Codex quota exceeded — handling task directly"
    # Do the work yourself
elif [ -f ".ai/codex_log_<name>.txt.done" ]; then
    # 4. Review: git diff, run tests, verify output
    git diff
fi
```

**Windows PowerShell — call ps1 directly (no Start-Process):**
```powershell
& ".claude\skills\codex-delegate\scripts\run_codex.ps1" `
    -Prompt "Read .ai/codex_task_<name>.md and execute all instructions." `
    -LogFile ".ai\codex_log_<name>.txt"

if (Test-Path ".ai\codex_log_<name>.txt.fallback_claude") {
    Write-Host "Codex quota exceeded — handling task directly"
} elseif (Test-Path ".ai\codex_log_<name>.txt.done") {
    Get-Content ".ai\codex_log_<name>.txt"
}
```
