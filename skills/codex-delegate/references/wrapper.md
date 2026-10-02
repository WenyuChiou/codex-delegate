# Codex wrapper reference

The `scripts/run_codex.sh` and `scripts/run_codex.ps1` wrappers run Codex CLI synchronously, detect quota / rate-limit failures, write sentinel files, and emit a machine-readable `<log>.result.json`.

## Invocation

### From Claude Code Bash (recommended)

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/run_codex.sh" \
  --brief-file .ai/codex_task_<name>.md \
  --repo "$PWD"
```

`${CLAUDE_PLUGIN_ROOT}` is resolved in a marketplace-loaded skill. For a
repository checkout, use `scripts/run_codex.sh`; for a direct portable skill,
use `<skill-root>/scripts/run_codex.sh`.

Optional flags:

- `--brief-file <path>`: on-disk brief, resolved absolutely (caller-first, then repo-relative); derives prompt/log when omitted
- `--prompt <text>`: explicit prompt override
- `--log-file <path>`: log/sentinel/result location; parent directory must exist
- `--repo <path>`: project root (default: the caller's `$PWD`)
- `--model <name>`: model string passed to `codex exec -m`
- `--output-file <path>`: passed to `codex exec -o`

### From PowerShell (direct call)

```powershell
& "<skill-root>\scripts\run_codex.ps1" `
    -BriefFile ".ai\codex_task_<name>.md" `
    -Repo (Get-Location).Path
```

PowerShell parameters: `-BriefFile` or `-Prompt`, `-Repo`, `-Model`, `-OutputFile`, `-LogFile`, `-Synchronous`. Marketplace hosts can resolve the plugin-root script instead.

**Do not** wrap these in `Start-Process`. Call them inline so file writes persist before the wrapper exits.

## Direct `codex exec` calls

If you skip the wrapper, close stdin explicitly to avoid a historical hang:

```bash
codex exec --sandbox workspace-write -m gpt-5.5 \
  "Read .ai/codex_task_<name>.md and execute all instructions inside." \
  < /dev/null > .ai/codex_log_<name>.txt 2>&1
```

Observed CLI `0.159.0-alpha.7` exposes `--sandbox workspace-write` and has no `--full-auto` or exec-local `--ask-for-approval` option. Sandbox selection is not blanket permission: the installed host's approval and policy settings still apply. `-C`/`--cd` means a working-root directory, not a context-file argument. See [runtime compatibility](runtime-compatibility.md) and the [official CLI reference](https://developers.openai.com/codex/cli/reference/).

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
