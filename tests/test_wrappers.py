"""Wrapper contract tests.

Bash test:
- Linux / macOS: `bash` from PATH, POSIX paths.
- Windows: explicitly use git-bash at `C:\\Program Files\\Git\\bin\\bash.exe`
  if present. Avoids WSL bash on PATH which (when no distro is installed,
  e.g. on GitHub Actions windows-latest) emits UTF-16 banner output that
  pollutes subprocess pipes. Skipif when git-bash isn't found so plain
  Windows hosts without Git for Windows skip cleanly instead of failing.

PowerShell test:
- Skipif when `powershell` isn't on PATH so the test is a no-op on
  Linux / macOS runners.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _resolve_bash() -> str | None:
    """Return a path to a bash interpreter we trust for the wrapper test.

    On Windows we explicitly prefer git-bash at the standard
    Git-for-Windows install path, because `shutil.which("bash")` may
    return WSL bash and WSL bash on a host without an installed distro
    prints a UTF-16 banner that contaminates subprocess pipes.
    """
    if sys.platform == "win32":
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if Path(candidate).is_file():
                return candidate
        return None
    return shutil.which("bash")


def to_bash_path(path: Path) -> str:
    """Convert a Path to a form bash can use on the current platform.

    Windows + git-bash: `C:\\Users\\foo` -> `/c/Users/foo` (drive letter
    becomes a top-level mount in MSYS2). Linux / macOS: POSIX path
    unchanged.
    """
    resolved = path.resolve()
    if sys.platform == "win32":
        drive = resolved.drive.rstrip(":").lower()
        tail = resolved.as_posix().split(":", 1)[1]
        return f"/{drive}{tail}"
    return resolved.as_posix()


_BASH = _resolve_bash()


@pytest.mark.skipif(_BASH is None, reason="bash (git-bash on Windows, system bash elsewhere) not available")
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
            _BASH,
            "-lc",
            (
                f"chmod +x '{to_bash_path(fake_codex)}' && "
                f"CODEX_PATH='{to_bash_path(fake_codex)}' "
                f"'{to_bash_path(Path(_BASH))}' '{to_bash_path(ROOT / 'scripts' / 'run_codex.sh')}' "
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
