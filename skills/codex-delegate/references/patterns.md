# Codex delegation patterns

Five recurring delegation shapes. Pick one before you write the task brief — the brief looks different for each.

For paste-ready invocations, see `examples.md`.

---

## 1. Context file

**When:** brief is long, will be re-run, or spans multiple files.

The default pattern. Step 1 of the Workflow in `SKILL.md` is exactly this.

Skeleton:

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

Launch via the wrapper as documented in `SKILL.md`.

---

## 2. Parallel execution

**When:** two or more independent subtasks on the same repo with no shared files.

Steps:

1. Write one task file per subtask: `.ai/codex_task_a.md`, `.ai/codex_task_b.md`, ...
2. From Claude Code Bash, launch each wrapper in parallel by issuing one Bash tool call per subtask in the same message, each with `run_in_background=true`. Distinct log paths so result files do not collide.
3. Poll each `.result.json` and aggregate before accepting.

If the subtasks share files, do not parallelise — sequence them, or use a router (`research-hub-multi-ai` for research-hub workflows, `agent-task-splitter` for generic rounds) to write a dependency-aware plan.

---

## 3. Resume session

**When:** previous Codex run produced ~80% of the desired output and you need a targeted fix-up.

Steps:

1. Confirm a recent session exists: `codex exec list --last 5`.
2. Resume with a corrective prompt:

   ```bash
   codex exec resume --last "Apply this fix-up: <specific instructions>." </dev/null
   ```

3. Or resume a specific session id:

   ```bash
   codex exec resume <session-id> "Address these review comments: <list>." </dev/null
   ```

Resume reuses the prior conversation, saving context. Do not resume across unrelated tasks — start a new session for those.

If resume is needed more than twice on the same task, the brief is wrong. Rewrite the task file (Pattern 1) instead of layering more fix-ups.

---

## 4. Structured output

**When:** Codex output will be consumed programmatically by Claude (data extraction, table generation, validation reports).

Steps:

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
   codex exec --sandbox workspace-write \
     --output-schema .ai/schemas/extraction_schema.json \
     "Extract <X> from <source> and emit conformant JSON." \
     </dev/null
   ```

3. Claude validates and post-processes the JSON. If validation fails, use Pattern 3 (resume) to refine.

---

## 5. Review mode

**When:** quick second opinion on the current working tree before commit.

Steps:

1. Stage the diff you want reviewed (`git add -p` or similar).
2. Run review mode:

   ```bash
   codex exec review --full-auto </dev/null
   ```

3. Read the review output as a hint, not a verdict. Claude still owns the acceptance decision and runs verification.

Review mode is cheaper than re-running the full implementation pattern when you only want a sanity check.

---

## When to stop delegating

If the task fits none of the five patterns cleanly, the brief is probably ambiguous or the work needs Claude's judgment more than Codex's throughput. Keep it in Claude.

If you would need three or more parallel runs (Pattern 2) coordinated against each other, the work belongs in a router (`research-hub-multi-ai` for research workflows, `agent-task-splitter` for generic ones), not in standalone Codex calls.
