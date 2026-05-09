# Codex wrapper output contract

Every wrapper run leaves machine-readable status at `<log-file>.result.json`. This is the *transport* contract; Claude still owns acceptance.

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
  "files_changed": [],
  "tests_run": [],
  "timestamp_utc": "2026-04-24T00:00:00Z"
}
```

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
