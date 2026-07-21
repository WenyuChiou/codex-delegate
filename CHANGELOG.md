# Changelog

All notable changes to `codex-delegate` (the Claude Code skill at
`WenyuChiou/codex-delegate`). Format:
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning:
[SemVer](https://semver.org/spec/v2.0.0.html).

This skill ships via the
[`WenyuChiou/ai-research-skills`](https://github.com/WenyuChiou/ai-research-skills)
marketplace; see that repo's CHANGELOG for the catalog-side history.

## [Unreleased]

### Added

- `references/handoff-protocol.md` — bidirectional Fable↔Codex rounds via
  `.ai/handoff/NNN_<slug>.to_codex.md` / `.to_fable.md` files (replaces
  clipboard transport); documents the harness-aware brief rule (do not
  re-teach discipline to repos carrying the fable-method-harness
  conditional pointer; Codex live probe 4/4 / 0/2 / 1/1), the
  `codex exec --json` exact-usage telemetry pattern, the Codex-app
  one-fixed-sentence flow with its cwd precondition, and the honest
  gitignore mechanics (Codex's file-read tool does not honor .gitignore —
  a future gitignore-honoring CLI needs stdin piping per the F1 lesson).
  SKILL.md gains a Harness-aware delegation section; output-contract.md
  gains the usage-telemetry section.

- `references/codex-prompt-blocks.md` — composable XML prompt blocks
  (`<verification_loop>`, `<grounding_rules>`, `<action_safety>`, …), four
  task recipes, and a prompt anti-pattern table for judgment-sensitive briefs.
  Adapted from the `gpt-5-4-prompting` skill in
  [`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc)
  (Apache-2.0); reframed for this skill's single-shot brief-file workflow.
- `tests/test_wrappers.py`: regression coverage for `files_changed` —
  populated on a git repo (bash + PowerShell) and `[]` on a non-git repo.

### Changed

- `SKILL.md` and `references/task-template.md` now point judgment-sensitive
  tasks (debugging, write-capable changes, review, research) at the new
  prompt-blocks reference; mechanical sweeps keep the flat template.
- `references/patterns.md` (Pattern 5) and `references/review-checklist.md`:
  added an explicit "do not auto-apply fixes from a review run — present
  findings and ask the user first" rule.
- `references/model-selection.md`: documented the `spark` shorthand
  (`--model gpt-5.3-codex-spark`).
- `scripts/run_codex.sh` and `scripts/run_codex.ps1` now auto-populate the
  `files_changed` field of `result.json`. The wrapper takes a
  `git status --porcelain` snapshot before and after the Codex run and diffs
  them, so `files_changed` attributes edits to that run only. It degrades to
  `[]` when the repo is not a git work tree, git is absent, or nothing
  changed. The wrapper's own log / sentinel / `result.json` files are written
  after the snapshot, so they never leak in.
- `references/output-contract.md`: documented which `result.json` fields the
  wrapper fills. `tests_run` and `risks` are deliberately *not* auto-filled —
  the wrapper cannot see tests run inside Codex's sandbox, and risk is a
  judgment call; both stay Claude's to fill during acceptance.

### Fixed

- `references/patterns.md` (Pattern 5): the review-mode code block used the
  deprecated `--full-auto` flag; replaced with `--sandbox workspace-write` to
  match `SKILL.md`, `wrapper.md`, and `examples.md`.
- `scripts/run_codex.ps1`: `Get-GitStatusSnapshot` returned `@($null)` (a
  1-element array holding `$null`) on a clean repo instead of a true empty
  array; now filters `$null` so the snapshot type is consistent. Latent
  fragility — downstream code absorbed it — fixed for robustness and parity
  with `gemini-delegate-skill`.

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
