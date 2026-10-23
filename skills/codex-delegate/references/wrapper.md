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
- `--effort <level|default>`: a level such as `low`, `medium`, `high` or `xhigh`, passed as `codex exec -c model_reasoning_effort=<level>`; `default` (or no flag and no `CODEX_DELEGATE_EFFORT`) passes nothing, so `~/.codex/config.toml` applies. The wrapper lowercases the value and exits 2 before Codex runs unless it is one word of letters; whether the model supports that level is left to Codex (an unsupported one fails with HTTP 400 and `status: error`).
- `--service-tier <value|default>`: a service tier such as `fast` or `flex`, passed as `codex exec -c service_tier="<value>"`; `default` (or no flag and no `CODEX_DELEGATE_SERVICE_TIER`) passes nothing, so `~/.codex/config.toml` applies. The wrapper lowercases the value and exits 2 before Codex runs unless it is one word of letters; whether the model supports that tier is not checked (see `model-selection.md`, "Service tier").
- `--sandbox <read-only|workspace-write>`: forwarded to Codex; default remains `workspace-write`
- `--output-file <path>`: passed to `codex exec -o`

### From PowerShell (direct call)

```powershell
& "<skill-root>\scripts\run_codex.ps1" `
    -BriefFile ".ai\codex_task_<name>.md" `
    -Repo (Get-Location).Path
```

PowerShell parameters: `-BriefFile` or `-Prompt`, `-Repo`, `-Model`, `-Sandbox`, `-OutputFile`, `-LogFile`, `-Synchronous`, `-Effort`, `-ServiceTier`. `-Effort` and `-ServiceTier` take the same values as `--effort` and `--service-tier` (pass them by name; `-ServiceTier` is declared last, after `-Effort`, so older positional calls keep their bindings). `-Sandbox` accepts `read-only` or `workspace-write`, with the existing `workspace-write` default. Marketplace hosts can resolve the plugin-root script instead.

**Do not** wrap these in `Start-Process`. Call them inline so file writes persist before the wrapper exits.

## Direct `codex exec` calls

If you skip the wrapper, close stdin explicitly to avoid a historical hang:

```bash
codex exec --sandbox workspace-write \
  "Read .ai/codex_task_<name>.md and execute all instructions inside." \
  < /dev/null > .ai/codex_log_<name>.txt 2>&1
```

Observed CLI `0.159.0-alpha.7` exposes `--sandbox workspace-write` and has no `--full-auto` or exec-local `--ask-for-approval` option. Sandbox selection is not blanket permission: the installed host's approval and policy settings still apply. `-C`/`--cd` means a working-root directory, not a context-file argument. See [runtime compatibility](runtime-compatibility.md) and the [official CLI reference](https://developers.openai.com/codex/cli/reference/).

The wrappers handle stdin closure and sandbox flag internally; direct `codex exec` calls do not.

Sandbox forwarding is a transport setting, not an independently enforced
permission boundary. The wrapper does not grant additional authority, audit
in-scope paths, or certify the installed Codex sandbox. Use `read-only` for an
inspection task when appropriate; the host's policies still apply.

## Environment variables

- `CODEX_PATH` — override the Codex executable (testing or custom envs)
- `CODEX_DELEGATE_EFFORT` — default for `--effort` / `-Effort` when the flag is absent or empty; the flag wins. Lets delegation run at a cheaper effort (for example `high`) without editing the interactive Codex config.
- `CODEX_DELEGATE_SERVICE_TIER` — default for `--service-tier` / `-ServiceTier` when the flag is absent or empty; the flag wins, and `default` passes nothing.
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
