# Codex wrapper reference

The `scripts/run_codex.sh` and `scripts/run_codex.ps1` wrappers run Codex CLI synchronously, detect quota / rate-limit failures, write sentinel files, and emit a machine-readable `<log>.result.json`.

## Invocation

### From Claude Code Bash (recommended)

```bash
bash scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." \
  --log-file .ai/codex_log_<name>.txt
```

Optional flags:

- `--repo <path>`: project root (default: the caller's `$PWD`)
- `--model <name>`: model string passed to `codex exec -m`
- `--output-file <path>`: passed to `codex exec -o`

### From PowerShell (direct call)

```powershell
& "C:\Users\wenyu\.claude\skills\codex-delegate\scripts\run_codex.ps1" `
    -Prompt "Read .ai/codex_task_<name>.md and execute all instructions inside." `
    -LogFile "C:\Users\wenyu\<repo>\.ai\codex_log_<name>.txt"
```

PowerShell parameters: `-Prompt` (required), `-Repo`, `-Model`, `-OutputFile`, `-LogFile`, `-Synchronous`.

**Do not** wrap these in `Start-Process`. Call them inline so file writes persist before the wrapper exits.

## Direct `codex exec` calls

If you skip the wrapper, close stdin explicitly to avoid a historical hang:

```bash
codex exec --sandbox workspace-write -m gpt-5.4 \
  "Read .ai/codex_task_<name>.md and execute all instructions inside." \
  < /dev/null > .ai/codex_log_<name>.txt 2>&1
```

Note: `--full-auto` is deprecated in codex CLI 0.128+. Use `--sandbox workspace-write`. There is no `--ask-for-approval` flag on `codex exec` (that flag is only on the top-level `codex` command); non-interactive mode auto-approves.

The wrappers handle stdin closure and sandbox flag internally; direct `codex exec` calls do not.

## Environment variables

- `CODEX_PATH` — override the Codex executable (testing or custom envs)
- `PYTHON_BIN` (bash only) — override the Python used for JSON escaping

## Sentinels written by the wrapper

| File | Meaning |
|---|---|
| `<log>.done` | Wrapper finished (success or fallback) |
| `<log>.error` | Wrapper hit hard failure or quota |
| `<log>.fallback_claude` | Quota exceeded; Claude must take over |
| `<log>.result.json` | Machine-readable status (always written) |

## Windows runner notes

Keep platform quirks in the runner scripts, not in the task brief:

- Claude Code Bash uses Unix shell syntax on Windows
- Use forward slashes in bash examples
- Use PowerShell examples only when calling `.ps1` directly
- Never use `Start-Process` for these wrappers from Claude Code sessions
