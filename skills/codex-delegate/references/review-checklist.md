# Codex delegate review checklist

Before accepting a Codex run, Claude must verify each of these:

## Brief quality

- [ ] Was the task file specific enough that a stranger could execute it?
- [ ] Did it list which files Codex was allowed to touch?
- [ ] Did it specify the verification commands?

## Execution scope

- [ ] Did Codex stay inside the allowed write scope?
- [ ] Are there any unexpected file additions or deletions?
- [ ] Did imports or downstream callers break?

## Diff quality

- [ ] Does the diff match the requested intent?
- [ ] Is the change idiomatic and consistent with adjacent code?
- [ ] Is anything obviously wrong, hallucinated, or under-tested?

## Verification

- [ ] Did the verification commands listed in the brief actually run?
- [ ] Did they pass?
- [ ] Were any flaky or skipped tests acknowledged?

## Risks and follow-ups

- [ ] Are risks or follow-ups obvious from the changes?
- [ ] Is anything left in a partially-migrated state?

## Decision

If any answer is *no*, fix the task file or take the rest locally in Claude. Do not paper over a bad run.
