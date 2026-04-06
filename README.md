# Codex CLI Delegation Skill

> [繁體中文版](README_zh-TW.md)

A Claude skill for delegating coding tasks to OpenAI's Codex CLI agent (GPT-5.4). Claude plans and reviews; Codex executes.

## Features

**Code Generation** — Bulk Python/backend code via `codex exec --full-auto` with workspace-write sandbox

**Code Review** — Automated review via `codex exec review`

**Test Generation** — Unit tests, integration tests, fixtures

**Multi-File Refactors** — Batch edits, constant extraction, renaming

**Cross-Platform** — Windows cmd shell workarounds included (write persistence fix)

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
