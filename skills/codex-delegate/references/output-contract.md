# Codex wrapper output contract

Every wrapper run leaves machine-readable status at `<log-file>.result.json`. This is the *transport* contract; Claude still owns acceptance.

## Exact usage telemetry (`codex exec --json`)

For cost accounting, prefer `codex exec --json` over log-size estimation:
canonical usage = `input + cache_read + cache_write + output` tokens, with
reasoning tokens reported separately (not folded into the total). This path
produced 7/7 exact usage rows in the fable-method-harness v3 activation
probe (2026-07-15) and is the recommended way to record per-round cost in
handoff replies (`references/handoff-protocol.md`).

## Schema

```json
{
  "status": "success|fallback|error",
  "delegate": "codex",
  "model": "codex/<model>",
  "log_file": "<path>",
  "output_file": "<path or empty>",
  "summary": "",
  "risks": [],
  "files_changed": ["path/changed_by_codex.py"],
  "tests_run": [],
  "timestamp_utc": "2026-04-24T00:00:00Z"
}
```

## Which fields the wrapper fills

| Field | Source | Notes |
|---|---|---|
| `status` / `delegate` / `model` / `log_file` / `output_file` / `summary` / `timestamp_utc` | wrapper | always written |
| `files_changed` | wrapper, **auto-derived** | `git status --porcelain` snapshot diff (before vs after the Codex run), so it attributes edits to *this run only*. Empty `[]` when the repo is not a git work tree, when git is absent, or when the run changed nothing. A file already dirty before the run, with an unchanged porcelain status line, is intentionally not re-reported — if you need the full picture regardless of pre-run state, run `git diff HEAD` yourself. The wrapper's own log / sentinel / `result.json` files are written *after* the snapshot, so they never leak in. |
| `tests_run` | **not auto-filled** — stays `[]` | The wrapper cannot see which tests ran: Codex runs them inside its own sandbox process and the wrapper only captures stdout. Treat `tests_run` as Claude's to fill during acceptance — run the brief's verification commands yourself and record them. |
| `risks` | **not auto-filled** — stays `[]` | Risk assessment is a judgment call; it stays Claude's job. |

## Status semantics

| Status | Meaning | Claude's next move |
|---|---|---|
| `success` | Codex exited 0; no quota or hard error detected | Read the diff, run verification, decide acceptance |
| `fallback` | Codex hit quota / rate limit | Take the work over directly in Claude |
| `error` | Codex exited non-zero with a hard failure | Read `<log>.error` and `<log>` to diagnose |

## Quota fallback sentinel

When the wrapper detects a quota or rate-limit failure, it writes a sibling `<log-file>.fallback_claude` sentinel file alongside the log and sets `result.json` `status` to `fallback`. Claude must then:

1. Read the sentinel and `result.json` to confirm the fallback path.
2. Take the work over directly in the current session, using the same task brief.
3. Not retry the Codex call — quota errors do not resolve quickly, and retry loops just burn context.

The sentinel is a marker, not a payload. Its presence + the `fallback` status are the contract; its content is informational.

## Why `success` is not acceptance

The wrapper only proves the delegate run finished. It does not verify:

- whether the diff matches your brief
- whether tests actually pass
- whether scope was respected
- whether the change is safe to ship

Always reopen the changed files, run the verification commands listed in the task brief, and only then declare success.
