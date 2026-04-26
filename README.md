# Codex Delegate

> [繁體中文](README_zh-TW.md)

`codex-delegate` is a Claude-oriented skill for using Codex CLI as an execution specialist for implementation-heavy coding work while keeping planning, review, and acceptance in Claude.

## Positioning

This skill is for tasks that are expensive in tokens but cheap in judgment:

- multi-file implementation
- mechanical refactors
- boilerplate generation
- test scaffolding
- large batch edits

It is not meant for architecture, root-cause debugging, security review, or ambiguous product decisions.

## What Changed In This Version

- clearer routing boundary between Claude, Codex, and Gemini
- explicit supervisor acceptance gate
- machine-readable wrapper output via `<log>.result.json`
- regression tests for bash and PowerShell wrappers

## Core Pattern

1. Claude writes a task file describing scope and constraints.
2. Claude launches Codex synchronously through the wrapper.
3. The wrapper emits sentinel files plus `result.json`.
4. Claude reviews the diff and runs verification before accepting the result.

Wrapper success is not final acceptance. Claude still owns the judgment.

## Repository Layout

```text
codex-delegate/
├── SKILL.md
├── README.md
├── README_zh-TW.md
├── scripts/
│   ├── run_codex.sh
│   └── run_codex.ps1
├── tests/
│   └── test_wrappers.py
└── references/
```

## Testing

```bash
python -m pytest -q
```

Current wrapper tests cover:

- success-path `result.json` generation
- PowerShell wrapper contract behavior

## Installation

**1. Install the skill** via the [`ai-research-skills` Claude Code marketplace](https://github.com/WenyuChiou/ai-research-skills):

```bash
claude plugin marketplace add WenyuChiou/ai-research-skills
claude plugin install codex-delegate@ai-research-skills
```

Default scope is `user` (this OS account, all projects). Add
`--scope project` to install only for the current project.

**2. Make sure Codex CLI is on `$PATH`:**

```bash
npm install -g @openai/codex
codex --version
```

## License

MIT
