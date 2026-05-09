# Codex delegation targets

## Routing summary

| Route to | Best for | Avoid |
|----------|----------|-------|
| `Codex` | Multi-file implementation, boilerplate, test scaffolds, mechanical refactors, batch edits | Architecture, debugging root cause, security review |
| `Claude` | Requirements, design, API contracts, bug diagnosis, acceptance review | Large repetitive edits |
| `Gemini` | Large-context reading, CJK / bilingual synthesis, second-opinion review | Bulk code generation, architecture decisions, security-sensitive coding |

If the task needs deep project memory, cross-conversation judgment, or nuanced tradeoffs, keep it in Claude.

## Good delegation targets

- Refactor a repeated pattern across 10+ files
- Generate unit tests from a clear implementation
- Add logging, docstrings, or type hints at scale
- Rename imports, constants, or terminology across a codebase
- Produce deterministic scaffolding from a precise spec
- Apply a known-good lint or style fix to many files at once

## Bad delegation targets

- Diagnose an intermittent production bug
- Decide between competing architectures
- Review auth, secrets, validation, or permission logic
- Resolve unclear requirements through conversation
- Make claims that need human defensibility or project memory
- Anything where "the answer requires asking the user a follow-up question"

## Decision rule of thumb

Delegate when the brief can be written in one shot and the diff can be reviewed objectively. Keep it in Claude when the brief itself needs negotiation, or the result needs context-aware judgment.
