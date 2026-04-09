# Codex Delegation Examples

## Example 1: Extract Constants

```bash
cd /d C:\Users\wenyu\mispricing-engine && echo Extract all magic numbers from pipeline/risk_controls.py into named constants in pipeline/strategy_constants.py. Add descriptive names and comments. Update imports in risk_controls.py. | codex exec --full-auto
```

## Example 2: Generate Unit Tests

**Context file** (`task-tests.md`):
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

```bash
cd /d C:\Users\wenyu\mispricing-engine && type task-tests.md | codex exec --full-auto
```

## Example 3: Code Review

```bash
cd /d C:\Users\wenyu\mispricing-engine && codex exec review --full-auto
```

## Example 4: Multi-File Refactor

```bash
cd /d C:\Users\wenyu\mispricing-engine && echo Rename all occurrences of kelly_optimizer to position_sizer across the entire codebase. Update imports, function calls, and string references. Do NOT rename the actual files. | codex exec --full-auto
```
