# Example CLAUDE.md Delegation Rules

Copy the section below into your project's `CLAUDE.md` to enable automatic delegation.
Adjust the paths and examples to match your project's structure.

---

## Delegation Rules (IMPORTANT)

- **Read `.claude/skills/codex-delegate/SKILL.md` before any task with 100+ lines of code changes.**
- Token-heavy Python/backend work (tests, boilerplate, batch edits, migrations) → delegate to Codex CLI
- Chinese/CJK content (reports, comments, translated docs) → auto-routes to Gemini CLI via helper script
- Architecture decisions, bug diagnosis, security, multi-subsystem coupling → keep in Claude
- Claude's role: **plan → write context file → launch Codex/Gemini → review output → fix remaining issues**

### Decision Matrix

| Task | Where |
|------|-------|
| Write tests for an existing module | Codex |
| Batch rename a function across 15 files | Codex |
| Add type hints to an entire package | Codex |
| Generate a README from structured data | Codex |
| Migrate deprecated API calls across the codebase | Codex |
| Generate Chinese-language report from data | Gemini (auto-routed) |
| Design a new module's API surface | Claude |
| Debug a subtle race condition | Claude |
| Write auth middleware | Claude |
| Refactor code that touches 3+ subsystems | Claude |

### Execution Pattern

**From Claude Code (bash):**
```bash
# 1. Write context file
# 2. Launch Codex
codex exec --full-auto -C "${REPO_ROOT:-.}" -m "${CODEX_MODEL:-gpt-5.4}" \
  "Read .ai/codex_task_<name>.md and execute all instructions."
# 3. Review: git diff, run tests, verify output
```

**From Cowork (Windows PowerShell):**
```powershell
# For read-only analysis:
$script = "$env:SKILL_ROOT\scripts\run_codex.ps1"
Start-Process powershell -ArgumentList "-File `"$script`" -Prompt `"Read .ai/codex_task_foo.md and execute.`" -Repo `"$env:REPO_ROOT`" -LogFile `"$env:REPO_ROOT\.ai\log_foo.txt`"" -WindowStyle Hidden

# For file writes — delegate to a Claude Code task:
# start_code_task: "Run codex exec --full-auto -C . 'Read .ai/codex_task_foo.md and execute.' then verify with git diff."
```

**Mac/Linux equivalent:**
```bash
./scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_foo.md and execute." \
  --repo "${REPO_ROOT:-.}" \
  --log-file ".ai/log_foo.txt" &

# Poll for completion
while [[ ! -f ".ai/log_foo.txt.done" ]]; do sleep 10; done
cat ".ai/log_foo.txt"
```
