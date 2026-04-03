# Task: <Descriptive Task Name>
#
# INSTRUCTIONS FOR USE:
#   1. Copy this file to .ai/codex_task_<name>.md in your repo
#   2. Fill in each section below — be specific and include WHY not just WHAT
#   3. Launch with:
#      codex exec --full-auto -C /path/to/repo -m gpt-5.4 "Read .ai/codex_task_<name>.md and execute all instructions."
#   4. Review output, run tests, then commit if correct

## Context

- Repo root: (Codex reads from its working directory — set via the -C flag when launching)
- Task type: [test generation / batch edit / migration / boilerplate / analysis]
- Key files to READ:
  - `src/module_a.py`
  - `src/module_b.py`
  - `tests/test_existing.py`  (reference for test style)
- Key files to WRITE:
  - `tests/test_module_a.py`
  - `.ai/codex_result_<name>.md`  (summary of changes)

## Background

<!-- Why is this task needed? What problem does it solve? -->
<!-- Example: "We refactored the data loader in module_a.py and need test coverage before merging." -->

## Instructions

<!--
  Be explicit and step-by-step. Codex has no conversation history — everything it needs
  must be here. Include references to files by path, not by description.
-->

1. Read `src/module_a.py` to understand all public functions and their signatures.
2. Read `tests/test_existing.py` to understand the existing test style (fixtures, naming, assertions).
3. Generate pytest unit tests in `tests/test_module_a.py`:
   - Cover every public function
   - Include at least one happy-path and one edge-case test per function
   - Use fixtures for any repeated setup
   - Each test function must have a one-line docstring
4. Write a brief summary of what was generated to `.ai/codex_result_<name>.md`.

## Constraints

- Do NOT modify any files outside the listed write paths
- Follow the existing code style exactly (indentation, naming conventions, import order)
- Do not add dependencies that aren't already in requirements.txt / pyproject.toml
- If a function's behavior is ambiguous, add a comment in the test noting the assumption

## Expected Output

- `tests/test_module_a.py` — complete test file, all tests passing
- `.ai/codex_result_<name>.md` — summary: which functions were covered, any issues encountered

## Verification (for Claude to run after Codex completes)

```bash
# Run after Codex finishes:
cd /path/to/repo
python -m pytest tests/test_module_a.py -v
```
