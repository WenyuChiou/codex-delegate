# Codex-delegate in a router/leaves architecture

This skill is the **leaf** for Codex-side work. When a single round of work needs more than one delegate, a router writes the plan first and the leaves read their per-task brief from it.

## When to use this skill directly (no router)

- One round of work, one delegate (just Codex).
- The brief fits one task file; success criteria are simple ("tests pass", "no diff outside scope").
- No coordination with another agent's output needed.

## When a router is in front

Use a router any time **two or more** of the following are true in one round:

- Both Codex and Gemini will run.
- Two or more Codex sessions will run, with dependencies between them or shared files.
- A reconciliation step needs to compare outputs from multiple agents against shared success criteria.

Pick the router by the surrounding workflow:

| Router | Lives in | Plan artifact | Use when |
|---|---|---|---|
| `research-hub-multi-ai` | research-hub workflows | `.coord/multi_ai_plan.md` | The round is part of a research-hub task (literature ingest, paper writing, etc.) |
| `agent-task-splitter` | `agent-collab-skills` marketplace | `.coord/plan.yml` + `.ai/<agent>_task_<NNN>_<slug>.md` | Generic multi-agent rounds (no research-hub context) |

The router owns task splitting, dependency ordering, and reconciliation. The leaves (this skill, `gemini-delegate`) only own single-task execution. Do not hand-roll multi-agent coordination from inside this skill.

## How a leaf round looks

When a router has already written your task brief, the workflow shrinks:

1. **Read round context first**:
   - From `agent-task-splitter`: `cat .coord/plan.yml` to see other agents' tasks, dependencies, success criteria.
   - From `research-hub-multi-ai`: `cat .coord/multi_ai_plan.md` for the same.
2. **Read your task brief**: `.ai/codex_task_<NNN>_<slug>.md` (the path the router put it at).
3. **Run the wrapper as usual** (see `SKILL.md` workflow step 2).
4. **Emit `result.json` per the contract** so the reconciler can verify success criteria programmatically.

The brief itself follows `task-template.md`. The success-criteria checks happen at the reconciler level, not inside this skill.

## Anti-patterns

- A router plan with one task: misuse — use the leaf skill directly, skip the router.
- A leaf inventing its own dependencies: the plan is the source of truth; if a dependency is missing, fix the plan, do not silently add work.
- Mixing routers in the same round: pick one. `research-hub-multi-ai` is the right router only when the round is part of a research-hub workflow; `agent-task-splitter` covers everything else.

## Cross-references

- `patterns.md` — single-task delegation shapes (context file, parallel, resume, structured output, review mode).
- `wrapper.md` — the wrapper invocation that emits `result.json`.
- `output-contract.md` — `result.json` schema and the `.fallback_claude` quota sentinel.
