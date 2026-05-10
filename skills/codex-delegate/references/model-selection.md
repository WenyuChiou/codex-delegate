# Model Selection

The wrapper defaults to `-m gpt-5.4`. As of `codex-cli` 0.128.0, `gpt-5.5` is also available and works correctly. **The default has not been changed** because the choice is not free — see the trade-off table below — and the right choice depends on the task. Override per-call with `--model gpt-5.5` (bash wrapper) or `-Model gpt-5.5` (PowerShell), or pin a different default in `~/.codex/config.toml`:

```toml
[model]
default = "gpt-5.5"
```

## Trade-off snapshot

A/B run on a single `codex-delegate` invocation, identical prompt, fresh repo each side. Prompt: *"Write a Python function `fibonacci(n)` that returns the nth Fibonacci number using memoization. Include a 1-line docstring and a single inline comment explaining the base case. Output ONLY the function definition, no test code, no explanation."*

| Metric | `gpt-5.4` | `gpt-5.5` |
|---|---|---|
| Wall time | 12.4 s | 15.7 s (+27%) |
| Tokens used | 6,962 | 21,432 (×3.1) |
| Output | uses mutable default arg (`memo={0:0,1:1}`) — works but a known Python pitfall | closure with inner `_fib`, fresh `memo = {}` per outer call — idiomatically cleaner |
| `status` in `result.json` | `success` | `success` |

Both produced correct, runnable code. The semantic difference is style: `gpt-5.5` produced more idiomatic Python at significantly higher cost.

## When to opt in to `gpt-5.5`

- The output will be read by humans (production refactor, code-review prep, library code that ships).
- Idiomatic style or subtle correctness (closure vs mutable default, generator vs list, dataclass vs dict, etc.) matters more than throughput.
- The task is one-shot, not a sweep — the 3× token cost doesn't multiply across many calls.

## When to keep `gpt-5.4` (current default)

- Mechanical sweeps across many files (the wrapper's main use case): boilerplate, batch edits, scaffolding, test harness generation. Token cost compounds quickly across N calls; gpt-5.4 is enough for these.
- Token budget pressure (you are running parallel delegate sessions or the user has quota concerns).
- Wall-time pressure (interactive iteration, TDD-style loops).
- Time-to-first-byte matters more than the final-byte quality.

## How to A/B another task in your project

```bash
mkdir -p /tmp/codex-ab-test/{a,b}
PROMPT="<your task>"

bash ~/.claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "$PROMPT" --repo /tmp/codex-ab-test/a \
  --log-file /tmp/codex-ab-test/a/log.txt --model gpt-5.4

bash ~/.claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "$PROMPT" --repo /tmp/codex-ab-test/b \
  --log-file /tmp/codex-ab-test/b/log.txt --model gpt-5.5

diff /tmp/codex-ab-test/{a,b}/log.txt
cat /tmp/codex-ab-test/a/log.txt.result.json
cat /tmp/codex-ab-test/b/log.txt.result.json
```

Inspect the wall-time, `tokens used`, and the actual generated code. Whatever pattern you see in your representative task should drive the model choice for that pattern, not the lab-style rubric above.
