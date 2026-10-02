# Runtime and package compatibility

Checked 2026-10-02. Baseline source: `438f92e`, Claude manifest `0.1.0`.
This patch proposes manifest `0.1.1`; it is not a published release.

## Separate the host from the executor

| Surface | Package/contract | Verification |
|---|---|---|
| Claude marketplace plugin | `.claude-plugin/plugin.json`; `skills/codex-delegate/`; plugin-root wrappers | Offline JSON/layout checks; Claude CLI unavailable |
| Direct portable skill | Copy `skills/codex-delegate/`, including bundled scripts/references | Isolated-copy Bash execution against synthetic Codex stub |
| Native Codex plugin | Current OpenAI docs describe root `plugin.json`, a `.codex-plugin/plugin.json` fallback, and Claude-compatible manifests | CLI plugin help inspected; no install/cache/marketplace changes or actual loading test |
| Codex execution | Observed `codex-cli 0.159.0-alpha.7` | Version/help only; no paid model call |
| PowerShell | `run_codex.ps1` and packaged byte-identical mirror | Core 7.6.6 exercised on Linux; native Windows behavior unverified |

The native-plugin path is a separate host surface. A portable script test
cannot establish plugin registration or loading. No new native Codex manifest
is invented here, and loading this skill in a different host does not expand
its mechanical-only delegation boundary.

## Observed command contract

`codex exec --sandbox workspace-write -C <repo> -m <model> [ -o <file> ] <prompt>`
uses a directory as `-C`/`--cd`; it does not attach a context file. The wrapper
closes stdin. Its model option is explicit and therefore wins over CLI config
model defaults. Installed help has no `codex models` command; use the
interactive `/model` picker for account-specific availability.

The existing `success`/`fallback`/`error` result and sentinel contracts are
preserved. Success is still subject to supervisor diff review and verification.

## Comparable regression evidence

- An isolated skill-directory copy could not execute its advertised wrapper.
  The package now includes byte-identical Bash/PowerShell mirrors; a synthetic
  Bash invocation produces the usual result JSON without the repository root.
- A caller-relative brief accepted before `-C` could be inaccessible from
  Codex's different working root. The same stub case now receives an absolute
  brief and writes the log beside that accepted file. Repo-relative fallback
  remains supported, including spaces in the path.
- Unsupported model-list/config examples are pinned by a documentation test.

Run the complete required suite with `python -m pytest tests/ -q`.
PowerShell Core Linux passes are not native Windows passes. Authentication, model availability,
quota spending, live delegate edits, and actual host loading remain unexecuted.

## Primary sources

- [OpenAI CLI reference](https://developers.openai.com/codex/cli/reference/):
  working-root flag and current interactive model picker
- [OpenAI configuration reference](https://developers.openai.com/codex/config-reference/):
  string-valued model configuration and override precedence
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins):
  portable root manifest and compatibility layouts
- [Claude plugin manifest reference](https://code.claude.com/docs/en/plugins-reference):
  skill/script topology, plugin-root substitution, and version pinning

Current docs may redirect to newer documentation URLs; installed help is the
source of truth for the exact runtime tested. Manifest `0.1.1` distinguishes
updated packaged content for version-pinned installs; it does not itself
install, update, publish, or invalidate anyone's local cache.

PowerShell Core 7 on Linux is exercised with native command doubles; platform
temporary paths preserve the prompt when TEMP is unset. This does not certify
Windows PowerShell 5.1 or native Codex loading.
