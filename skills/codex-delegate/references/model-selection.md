# Model and Effort Selection

The wrapper has two optional knobs, and by default it turns neither:

| Knob | Bash / PowerShell | Passed to Codex as | Without it |
|---|---|---|---|
| Model | `--model <id>` / `-Model <id>` | `-m <id>` | `model` from `~/.codex/config.toml` (reported as `codex/default`) |
| Reasoning effort | `--effort <level>` / `-Effort <level>` | `-c model_reasoning_effort=<value>` | `model_reasoning_effort` from `~/.codex/config.toml` (reported as `default`) |

Since manifest `0.1.2` the wrapper passes no `-m` unless asked. Earlier versions always passed `-m gpt-5.5` (from commit `70e6fdc`, 2026-05-15), which fails with HTTP 400 on accounts that lose access to that model; the wrapper still has no built-in model id. Since manifest `0.1.3` it also passes no effort unless asked. Both Codex defaults live in `~/.codex/config.toml` as plain strings, not tables:

```toml
model = "<model id from the /model picker>"
model_reasoning_effort = "high"
```

This follows the [official configuration reference](https://developers.openai.com/codex/config-reference/). Model ids, effort levels and prices vary by account and CLI version; inspect the interactive `/model` picker rather than trusting any id written in a doc.

## Reasoning effort

Effort is not free: higher effort spends more reasoning tokens and wall time per call, and the cost compounds across a sweep of delegations. The interactive config is often set high for hands-on work, which then silently applies to every delegation too. Two ways to separate them:

- **Per call:** `--effort medium` (bash) / `-Effort medium` (PowerShell).
- **For all delegations:** set `CODEX_DELEGATE_EFFORT=high` in the environment that runs the wrapper. Precedence is flag, then `CODEX_DELEGATE_EFFORT`, then the Codex config. `--effort default` ignores the env var and passes nothing, so a single call can fall back to the config value.

The wrapper lowercases the value and only checks that it is one word of letters (anything else exits 2 before Codex runs); `default` means no override. Which levels exist depends on the model and the CLI, so the wrapper does not keep a list. On 2026-10-17 the local model cache listed `low` … `xhigh`, `max`, `ultra`, while the API's own error message named `none`, `minimal`, `low` … `xhigh`, `max`. An unsupported level fails with HTTP 400, which the wrapper reports as `status: error` (exit 1), not as a silent fallback.

Rough guide:

- `low` / `medium`: mechanical sweeps whose acceptance is a runnable check (rename across files, scaffold from a template, reformat).
- `high`: the usual delegated task, where the brief states the pattern and Claude reviews the diff.
- `xhigh`: one-shot tasks where subtle correctness matters and the extra cost does not multiply across many calls.
- `max` / `ultra`, where the model offers them: cost more than `xhigh`; rarely worth it for delegated mechanical work.

## Choosing a model

- Delegate to one of the newest models that is not the most expensive tier. Codex's own model list (`~/.codex/models_cache.json`, or the `/model` picker) describes each model; pick the current general-purpose "workhorse", not the "frontier" tier. Token cost compounds across N calls, and the brief plus Claude's review carry the judgment.
- Keep the frontier tier out of delegation. Work that needs that much judgment usually belongs with Claude, not with a delegate.
- Lower effort on the same model is often a cheaper first lever than switching to an older model.
- An explicit `--model` becomes `-m <id>` and overrides the config default for that call only.

## Historical trade-off snapshot (2026-05)

Kept as evidence of the cost gap between a cheaper and a pricier model; the two model ids are superseded. A/B run on a single `codex-delegate` invocation, identical prompt, fresh repo each side. Prompt: *"Write a Python function `fibonacci(n)` that returns the nth Fibonacci number using memoization. Include a 1-line docstring and a single inline comment explaining the base case. Output ONLY the function definition, no test code, no explanation."*

| Metric | `gpt-5.4` | `gpt-5.5` |
|---|---|---|
| Wall time | 12.4 s | 15.7 s (+27%) |
| Tokens used | 6,962 | 21,432 (×3.1) |
| Output | uses mutable default arg (`memo={0:0,1:1}`) — works but a known Python pitfall | closure with inner `_fib`, fresh `memo = {}` per outer call — idiomatically cleaner |
| `status` in `result.json` | `success` | `success` |

Both produced correct, runnable code. The pricier model wrote more idiomatic Python at about three times the tokens.

## The `spark` shorthand (historical)

`gpt-5.3-codex-spark` was a low-latency, low-cost Codex model. There is no alias
resolution in the wrapper — it passes `--model` straight through — so the
shorthand is a documentation convention: when the user (or a brief) says
**`spark`**, invoke the wrapper with `--model gpt-5.3-codex-spark`
(`-Model gpt-5.3-codex-spark` in PowerShell), after confirming in the `/model`
picker that the id still exists. For trivially mechanical, latency-bound work,
`--effort low` on your configured default is the version-independent
alternative.

## How to A/B another task in your project

Compare efforts on one model (or swap the two `--effort` flags for two `--model <id>` flags):

```bash
mkdir -p /tmp/codex-ab-test/{a,b}
PROMPT="<your task>"

bash "${CLAUDE_PLUGIN_ROOT}/scripts/run_codex.sh" \
  --prompt "$PROMPT" --repo /tmp/codex-ab-test/a \
  --log-file /tmp/codex-ab-test/a/log.txt --effort medium

bash "${CLAUDE_PLUGIN_ROOT}/scripts/run_codex.sh" \
  --prompt "$PROMPT" --repo /tmp/codex-ab-test/b \
  --log-file /tmp/codex-ab-test/b/log.txt --effort xhigh

diff /tmp/codex-ab-test/{a,b}/log.txt
cat /tmp/codex-ab-test/a/log.txt.result.json
cat /tmp/codex-ab-test/b/log.txt.result.json
```

Inspect the wall time, `tokens used`, and the actual generated code. Whatever pattern you see in your representative task should drive the choice for that pattern, not the rough guide above.
