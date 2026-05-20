# Changelog

All notable changes to `codex-delegate` (the Claude Code skill at
`WenyuChiou/codex-delegate`). Format:
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning:
[SemVer](https://semver.org/spec/v2.0.0.html).

This skill ships via the
[`WenyuChiou/ai-research-skills`](https://github.com/WenyuChiou/ai-research-skills)
marketplace; see that repo's CHANGELOG for the catalog-side history.

## [Unreleased]

## [0.1.0] - 2026-05-15

The initial published version. Captures the skill state at commit
[`3683671`](https://github.com/WenyuChiou/codex-delegate/commit/3683671)
("docs(model-selection): flip framing to reflect gpt-5.5 default"),
the HEAD on `master` when this CHANGELOG was first added.

### Included

- `SKILL.md` — Claude Code skill manifest. Triggers when Claude
  benefits from delegating token-heavy mechanical work (batch edits,
  scaffolding, refactors, test generation, plotting scripts) to the
  Codex CLI.
- `references/` — workflow patterns (`gpt-5.5` as default, `gpt-5.4`
  workaround for legacy callers, `--full-auto`-vs-`-s workspace-write`,
  stdin-close requirement on `codex-cli >= 0.121.0`, `.fallback_claude`
  quota mechanism, leaf role in the router/leaves multi-AI
  architecture, 5 paste-ready prompt templates).
- `tests/` — `pytest` covering the wrapper helpers + cross-platform
  shell invocation.
- `.github/workflows/test.yml` — runs `pytest` on push + PR
  (Ubuntu / Windows × Python 3.10 / 3.11 / 3.12 matrix).
- `LICENSE` — MIT.
- `.claude-plugin/plugin.json` so the root SKILL.md is picked up by
  the `WenyuChiou/ai-research-skills` marketplace.

### Model selection history

The wrapper default model changed during 0.x development:

- **2026-05-15** (commit
  [`70e6fdc`](https://github.com/WenyuChiou/codex-delegate/commit/70e6fdc)):
  default flipped `gpt-5.4 → gpt-5.5`. The skill documents both: the
  default for new callers (`gpt-5.5`), and the `-m gpt-5.4` workaround
  for legacy contexts where the older model is required.
- **PR
  [#1](https://github.com/WenyuChiou/codex-delegate/pull/1)** (merged
  2026-05-09): documented the `-m gpt-5.4` workaround, the
  stdin-close requirement, and the `.fallback_claude` quota mechanism.
  This is the upstream change that promoted the skill from `T2` to
  `T1` in the `ai-research-skills` catalog.

### Known limitations (as of 0.1.0)

- Tested by one graduate-student researcher; not corpus-scale validated.
- Codex CLI binary must be installed separately (`codex-cli >= 0.121.0`);
  the skill documents the install path but does not install it for you.
- Delegation is one-directional (Claude → Codex). Routing decisions
  among multiple Codex sessions are handled by `research-hub-multi-ai`
  in the `ai-research-skills` catalog, not by this skill alone.

[Unreleased]: https://github.com/WenyuChiou/codex-delegate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/WenyuChiou/codex-delegate/releases/tag/v0.1.0
