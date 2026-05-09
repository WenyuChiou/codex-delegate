"""Wrapper contract tests.

The bash test runs on any platform that has `bash` on PATH (Linux,
macOS, Windows-with-git-bash, Windows-with-WSL). On Windows the test
detects whether the bash on PATH is git-bash (`/c/Users/...`) or WSL
(`/mnt/c/Users/...`) and translates paths accordingly. On Linux / macOS
it passes POSIX paths through unchanged.

The PowerShell test is skipped where `powershell` is not on PATH so it
is a no-op on Linux / macOS CI runners.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _bash_drive_prefix() -> str:
    """Probe whether the bash on PATH is WSL or git-bash.

    Returns `/mnt` for WSL, `""` for git-bash. Linux / macOS don't have
    drive letters at all so this helper isn't used there.
    """
    if sys.platform != "win32":
        return ""
    if shutil.which("bash") is None:
        return ""
    proc = subprocess.run(
        ["bash", "-c", "test -d /mnt/c && echo /mnt || echo ''"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def to_bash_path(path: Path) -> str:
    """Convert a Path to a form bash can use on the current platform.

    Windows + git-bash: `C:\\Users\\foo` -> `/c/Users/foo`.
    Windows + WSL bash: `C:\\Users\\foo` -> `/mnt/c/Users/foo`.
    Linux / macOS: POSIX path returned unchanged.
    """
    resolved = path.resolve()
    if sys.platform == "win32":
        prefix = _bash_drive_prefix()
        drive = resolved.drive.rstrip(":").lower()
        tail = resolved.as_posix().split(":", 1)[1]
        return f"{prefix}/{drive}{tail}"
    return resolved.as_posix()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
def test_run_codex_sh_writes_result_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho 'delegate ok'\n", encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    log_file = repo / ".ai" / "codex_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = to_bash_path(fake_codex)

    proc = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"chmod +x '{to_bash_path(fake_codex)}' && "
                f"CODEX_PATH='{to_bash_path(fake_codex)}' "
                f"bash '{to_bash_path(ROOT / 'scripts' / 'run_codex.sh')}' "
                f"--prompt 'do work' "
                f"--repo '{to_bash_path(repo)}' "
                f"--log-file '{to_bash_path(log_file)}'"
            ),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(log_file.with_suffix(log_file.suffix + ".result.json").read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"
    assert result["delegate"] == "codex"
    assert result["model"] == "codex/gpt-5.4"
    assert result["log_file"].endswith("/repo/.ai/codex_log.txt")
    assert (repo / ".ai" / "codex_log.txt.done").exists()


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
def test_run_codex_ps1_writes_result_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text("@echo off\r\necho delegate ok\r\n", encoding="utf-8")

    log_file = repo / ".ai" / "codex_ps_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "run_codex.ps1"),
            "-Prompt",
            "do work",
            "-Repo",
            str(repo),
            "-LogFile",
            str(log_file),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(log_file.with_suffix(log_file.suffix + ".result.json").read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"
    assert result["delegate"] == "codex"
    assert result["model"] == "codex/gpt-5.4"
