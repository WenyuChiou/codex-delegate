# Codex CLI Delegation Skill

> [繁體中文版](README_zh-TW.md)

A Claude skill for delegating coding tasks to OpenAI's Codex CLI agent (GPT-5.4). Claude plans and reviews; Codex executes.

## Why this exists

In real coding workflows, some tasks are better handled outside the main Claude Code session, especially when they are:

- implementation-heavy
- repetitive
- large in scope
- better isolated in a separate execution flow

`codex-delegate` was built to make that handoff easier.

## Features

**Code Generation** — Bulk Python/backend code via `codex exec --full-auto` with workspace-write sandbox

**Code Review** — Automated review via `codex exec review`

**Test Generation** — Unit tests, integration tests, fixtures

**Multi-File Refactors** — Batch edits, constant extraction, renaming

**Cross-Platform** — Windows cmd shell workarounds included (write persistence fix)

## Common use cases

- delegate large refactors to Codex CLI
- offload repetitive file edits
- use Claude Code for planning and Codex for execution
- reduce token consumption in long coding sessions
- build multi-model development workflows
  
## Setup

Codex CLI must be installed globally:

```bash
npm install -g @openai/codex
```

Verify: `codex --version` (tested with v0.104.0)

## Project Structure

```
codex-delegate/
├── SKILL.md              # Main skill instructions
├── README.md             # English documentation
├── README_zh-TW.md       # 繁體中文文件
└── references/
    └── examples.md       # Complete delegation examples
```

## License

MIT
