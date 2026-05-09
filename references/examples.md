# Codex Delegation Examples

Examples are written for Claude Code Bash on Windows (git-bash). Use forward-slash paths and POSIX commands. For PowerShell, see `scripts/run_codex.ps1`.

For prompt-template skeletons of the five workflow patterns, see `patterns.md`.

## Example 1: Extract Constants (inline prompt)

```bash
cd /c/Users/wenyu/mispricing-engine && \
  echo "Extract all magic numbers from pipeline/risk_controls.py into named constants in pipeline/strategy_constants.py. Add descriptive names and comments. Update imports in risk_controls.py." \
  | codex exec --full-auto -m gpt-5.4
```

## Example 2: Generate Unit Tests (context file)

Context file (`.ai/codex_task_tests.md`):

```markdown
# Task: Generate unit tests for conviction_scorer.py

## Goal
Create tests/test_conviction_scorer.py with pytest tests covering:
- compute_conviction() with various input combinations
- route_strategy() decision tree (all 5 gates)
- Edge cases: missing data, extreme values, None inputs

## Requirements
- Use pytest fixtures for common test data
- Mock external dependencies (MoodRing API, etc.)
- Test boundary conditions for SKIP_THRESHOLD (50) and ROUTE_THRESHOLD (55)
- At least 15 test cases
```

Launch:

```bash
cd /c/Users/wenyu/mispricing-engine && \
  cat .ai/codex_task_tests.md | codex exec --full-auto -m gpt-5.4
```

## Example 3: Code Review (review mode)

```bash
cd /c/Users/wenyu/mispricing-engine && \
  codex exec review --full-auto -m gpt-5.4 < /dev/null
```

`< /dev/null` is required when no stdin is piped, on `codex-cli >= 0.121.0`.

## Example 4: Multi-File Refactor (inline prompt)

```bash
cd /c/Users/wenyu/mispricing-engine && \
  echo "Rename all occurrences of kelly_optimizer to position_sizer across the entire codebase. Update imports, function calls, and string references. Do NOT rename the actual files." \
  | codex exec --full-auto -m gpt-5.4
```

## Example 5: Parallel Execution (independent subtasks)

Two independent subtasks, run from Claude in parallel using `run_in_background=true` on each Bash call. Distinct log paths prevent collision.

Subtask A — generate tests:

```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_tests.md and execute all instructions inside." \
  --log-file .ai/codex_log_tests.txt
```

Subtask B — refactor imports:

```bash
bash .claude/skills/codex-delegate/scripts/run_codex.sh \
  --prompt "Read .ai/codex_task_imports.md and execute all instructions inside." \
  --log-file .ai/codex_log_imports.txt
```

After both finish, inspect `.ai/codex_log_tests.txt.result.json` and `.ai/codex_log_imports.txt.result.json` separately.

If the subtasks share files, do not parallelise — sequence them, or use `research-hub-multi-ai` to write a dependency-aware plan.

## Example 6: Resume Session (targeted fix-up)

When the previous run produced ~80% of the desired output and you only need a fix-up:

```bash
codex exec resume --last \
  "Apply these review comments: (1) move helper to utils.py, (2) replace bare except, (3) add type hints to public functions." \
  < /dev/null
```

Resume specific session id:

```bash
codex exec resume <session-id> \
  "Address only the failing test in test_strategy.py::test_threshold_boundary." \
  < /dev/null
```

Resume reuses the prior conversation. Do not resume across unrelated tasks.
