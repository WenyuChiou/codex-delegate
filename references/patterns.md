# Codex Delegation Patterns

Ready-to-paste templates for the five workflow patterns referenced in `SKILL.md`. Replace `<...>` placeholders with your real values.

---

## Pattern 1: Context File

**When:** the brief is long, spans multiple files, or you want to re-run it without retyping.

**Steps:**

1. Write `.ai/codex_task_<name>.md` with this skeleton:

   ```markdown
   # Task: <descriptive name>

   ## Context
   - Repo: <absolute path>
   - Read these files first:
     - <path/a>
     - <path/b>
   - Only modify:
     - <path/c>

   ## Goal
   <one paragraph: what should exist when you are done>

   ## Constraints
   - Do not edit files outside the allowed list
   - Follow adjacent code style
   - Preserve public APIs unless told otherwise

   ## Acceptance
   - Required tests: <commands>
   - Required result summary: write to .ai/codex_result_<name>.md
   ```

2. Launch with the wrapper:

   ```bash
   bash .claude/skills/codex-delegate/scripts/run_codex.sh \
     --prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." \
     --log-file .ai/codex_log_<name>.txt
   ```

3. After the run, check `.ai/codex_log_<name>.txt.result.json` and the resulting diff before accepting.

---

## Pattern 2: Parallel Execution

**When:** two or more independent subtasks on the same repo with no shared files.

**Steps:**

1. Write one task file per subtask: `.ai/codex_task_a.md`, `.ai/codex_task_b.md`, ...
2. From Claude Code Bash, launch each wrapper in parallel by issuing one Bash tool call per subtask in the same message, each with `run_in_background=true`. Use distinct log paths so the result files do not collide.
3. Poll each `.result.json` and aggregate before accepting.

Boilerplate launch:

```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_a.md and execute all instructions inside." \
  --log-file .ai/codex_log_a.txt
```

```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_b.md and execute all instructions inside." \
  --log-file .ai/codex_log_b.txt
```

If the subtasks share files, do not parallelise — sequence them or use `research-hub-multi-ai` to write a dependency-aware plan.

---

## Pattern 3: Resume Session

**When:** previous Codex run produced ~80% of the desired output and you need targeted fix-up rather than a fresh start.

**Steps:**

1. Confirm there is a recent session to resume: `codex exec list --last 5`.
2. Resume the most recent session with a corrective prompt:

   ```bash
   codex exec resume --last "Apply this fix-up: <specific instructions>." < /dev/null
   ```

3. Or resume a specific session id:

   ```bash
   codex exec resume <session-id> "Address these review comments: <list>." < /dev/null
   ```

Resume reuses the prior conversation, saving context. Do not resume across unrelated tasks — start a new session for those.

---

## Pattern 4: Structured Output

**When:** Codex output will be consumed programmatically by Claude (data extraction, table generation, validation reports).

**Steps:**

1. Define a JSON schema, e.g. `.ai/schemas/extraction_schema.json`:

   ```json
   {
     "type": "object",
     "properties": {
       "items": {
         "type": "array",
         "items": {
           "type": "object",
           "properties": {
             "id":    { "type": "string" },
             "value": { "type": "number" }
           },
           "required": ["id", "value"]
         }
       }
     },
     "required": ["items"]
   }
   ```

2. Force-schema run:

   ```bash
   codex exec --full-auto \
     --output-schema .ai/schemas/extraction_schema.json \
     "Extract <X> from <source> and emit conformant JSON." \
     < /dev/null
   ```

3. Claude validates and post-processes the JSON. If validation fails, use Pattern 3 (resume) to refine.

---

## Pattern 5: Review Mode

**When:** quick second opinion on the current working tree, before commit.

**Steps:**

1. Stage the diff you want reviewed (`git add -p` or similar).
2. Run review mode:

   ```bash
   codex exec review --full-auto < /dev/null
   ```

3. Read the review output as a hint, not a verdict. Claude still owns the acceptance decision and runs verification.

Review mode is cheaper than re-running the full implementation pattern when you only want a sanity check.

---

## When to Stop Delegating

If you find yourself reaching for resume more than twice on the same task, the brief is wrong. Rewrite the task file (Pattern 1) instead of layering more fix-ups.

If you would need three or more parallel runs (Pattern 2) coordinated against each other, the work belongs in a router (`research-hub-multi-ai`), not in standalone Codex calls.
