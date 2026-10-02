"""Skill-package checks require no host login or live model calls."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["run_codex.sh", "run_codex.ps1"])
def test_skill_package_bundles_canonical_wrapper(filename):
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    skill = ROOT / "skills" / manifest["name"]
    assert (skill / "SKILL.md").is_file()
    packaged = skill / "scripts" / filename
    assert packaged.is_file(), f"advertised skill-relative wrapper missing: {filename}"
    assert packaged.read_bytes() == (ROOT / "scripts" / filename).read_bytes()


def test_model_guidance_uses_supported_command_and_config_shape():
    skill = (ROOT / "skills/codex-delegate/SKILL.md").read_text(encoding="utf-8")
    selection = (ROOT / "skills/codex-delegate/references/model-selection.md").read_text(encoding="utf-8")
    assert "codex models" not in skill + selection
    assert '[model]\ndefault = ' not in selection
    assert 'model = "gpt-5.4"' in selection
    assert "explicit" in selection and "-m" in selection


def test_noninteractive_sandbox_does_not_advertise_blanket_approval():
    skill = (ROOT / "skills/codex-delegate/SKILL.md").read_text(encoding="utf-8")
    assert "auto-approves" not in skill
    assert "Sandbox selection is not blanket permission" in skill
    assert "approval and policy settings still apply" in skill
