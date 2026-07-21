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
    assert result["model"] == "codex/gpt-5.5"
    assert result["log_file"].endswith("/repo/.ai/codex_log.txt")
    assert (repo / ".ai" / "codex_log.txt.done").exists()


@pytest.mark.skipif(_BASH is None, reason="bash (git-bash on Windows, system bash elsewhere) not available")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_run_codex_sh_reports_files_changed(tmp_path: Path) -> None:
    """files_changed is auto-derived from a git porcelain snapshot diff."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    # Fake codex writes a file into the repo. Arg 5 is the `-C <repo>` value
    # (codex args: exec --sandbox workspace-write -C <repo> -m <model> <prompt>).
    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        'echo "delegated content" > "$5/delegated_file.txt"\n'
        "echo 'delegate ok'\n",
        encoding="utf-8",
        newline="\n",
    )
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
    assert result["files_changed"] == ["delegated_file.txt"]


@pytest.mark.skipif(_BASH is None, reason="bash (git-bash on Windows, system bash elsewhere) not available")
def test_run_codex_sh_files_changed_empty_when_not_git(tmp_path: Path) -> None:
    """files_changed degrades to [] when the repo is not a git work tree."""
    repo = tmp_path / "repo"
    repo.mkdir()  # deliberately NOT a git repo

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        'echo "delegated content" > "$5/delegated_file.txt"\n'
        "echo 'delegate ok'\n",
        encoding="utf-8",
        newline="\n",
    )
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
    assert result["files_changed"] == []


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_run_codex_ps1_reports_files_changed(tmp_path: Path) -> None:
    """PowerShell wrapper: files_changed is auto-derived from git porcelain."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    # Fake codex writes a file into the repo. %~5 is the `-C <repo>` value.
    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text(
        "@echo off\r\n"
        'echo delegated content>"%~5\\delegated_file.txt"\r\n'
        "echo delegate ok\r\n",
        encoding="utf-8",
    )

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
    assert result["files_changed"] == ["delegated_file.txt"]


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
def test_run_codex_ps1_files_changed_empty_when_not_git(tmp_path: Path) -> None:
    """PS wrapper: files_changed degrades to [] when the repo is not a git work tree."""
    repo = tmp_path / "repo"
    repo.mkdir()  # deliberately NOT a git repo

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text(
        "@echo off\r\n"
        'echo delegated content>"%~5\\delegated_file.txt"\r\n'
        "echo delegate ok\r\n",
        encoding="utf-8",
    )

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
    assert result["files_changed"] == []


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
    assert result["model"] == "codex/gpt-5.5"


# --- Brief discipline guard tests (added 2026-05-15) ---
#
# These pin down the behavior introduced to fix the auditability gap that the
# research-hub v0.89.1 post-release audit found: inline --prompt dispatches
# with no brief on disk left orphan results that couldn't be traced back.

def _run_sh(repo: Path, fake_codex: Path, extra_args: list[str], env_extra: dict[str, str] | None = None):
    env = os.environ.copy()
    env["CODEX_PATH"] = to_bash_path(fake_codex)
    if env_extra:
        env.update(env_extra)
    cmd_args = " ".join(f"'{a}'" for a in extra_args)
    return subprocess.run(
        [
            _BASH,
            "-lc",
            (
                f"chmod +x '{to_bash_path(fake_codex)}' && "
                f"CODEX_PATH='{to_bash_path(fake_codex)}' "
                + (f"CODEX_DELEGATE_ALLOW_INLINE='{env_extra['CODEX_DELEGATE_ALLOW_INLINE']}' "
                   if env_extra and "CODEX_DELEGATE_ALLOW_INLINE" in env_extra else "")
                + f"'{to_bash_path(Path(_BASH))}' '{to_bash_path(ROOT / 'scripts' / 'run_codex.sh')}' "
                f"--repo '{to_bash_path(repo)}' {cmd_args}"
            ),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_brief_file_canonical_log_path(tmp_path: Path) -> None:
    """--brief-file should auto-derive log path next to brief (no --log-file needed)."""
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    brief = repo / ".ai" / "codex_task_v090_audit.md"
    brief.write_text("# Brief\nDo X.\n", encoding="utf-8")

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho 'delegate ok'\n", encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    proc = _run_sh(repo, fake_codex, ["--brief-file", to_bash_path(brief)])

    assert proc.returncode == 0, proc.stderr
    canonical_log = repo / ".ai" / "codex_task_v090_audit.txt"
    canonical_result = repo / ".ai" / "codex_task_v090_audit.txt.result.json"
    assert canonical_log.exists(), f"canonical log missing: {canonical_log}"
    assert canonical_result.exists(), f"canonical result.json missing: {canonical_result}"
    result = json.loads(canonical_result.read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_inline_long_prompt_without_brief_is_refused(tmp_path: Path) -> None:
    """Inline --prompt > 500 chars with no brief reference must exit 2."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho should-not-run\n", encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    long_prompt = "x" * 600  # no codex_task_*.md reference anywhere
    proc = _run_sh(repo, fake_codex, ["--prompt", long_prompt])

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}; stderr={proc.stderr}"
    assert "brief must be on disk" in proc.stderr
    assert "CODEX_DELEGATE_ALLOW_INLINE" in proc.stderr


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_escape_hatch_bypasses_guard(tmp_path: Path) -> None:
    """CODEX_DELEGATE_ALLOW_INLINE=1 must let long inline prompts through."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho 'delegate ok'\n", encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    long_prompt = "x" * 600
    log_file = repo / ".ai" / "codex_log.txt"
    proc = _run_sh(
        repo,
        fake_codex,
        ["--prompt", long_prompt, "--log-file", to_bash_path(log_file)],
        env_extra={"CODEX_DELEGATE_ALLOW_INLINE": "1"},
    )

    assert proc.returncode == 0, proc.stderr
    assert (repo / ".ai" / "codex_log.txt.result.json").exists()


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_prompt_with_existing_brief_reference_is_allowed(tmp_path: Path) -> None:
    """Long inline prompt that references an EXISTING brief on disk must pass."""
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    brief = repo / ".ai" / "codex_task_legacy.md"
    brief.write_text("# Brief\nDo X.\n", encoding="utf-8")

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho 'delegate ok'\n", encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    # 600-char prompt that contains a `Read .ai/codex_task_legacy.md` reference
    long_prompt = (
        "Read .ai/codex_task_legacy.md and execute. " + ("filler text " * 50)
    )
    assert len(long_prompt) > 500
    log_file = repo / ".ai" / "codex_log.txt"
    proc = _run_sh(repo, fake_codex, ["--prompt", long_prompt, "--log-file", to_bash_path(log_file)])

    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_prompt_referencing_missing_brief_is_refused(tmp_path: Path) -> None:
    """Long inline prompt referencing a brief that does NOT exist must exit 2."""
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho should-not-run\n", encoding="utf-8", newline="\n")
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    long_prompt = (
        "Read .ai/codex_task_missing.md and execute. " + ("filler text " * 50)
    )
    proc = _run_sh(repo, fake_codex, ["--prompt", long_prompt])

    assert proc.returncode == 2, proc.stderr
    assert "does not exist on disk" in proc.stderr


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
def test_run_codex_ps1_brief_file_canonical_path(tmp_path: Path) -> None:
    """PowerShell parity: -BriefFile auto-derives log path next to brief."""
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    brief = repo / ".ai" / "codex_task_v090_ps_audit.md"
    brief.write_text("# Brief\nDo X.\n", encoding="utf-8")

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text("@echo off\r\necho delegate ok\r\n", encoding="utf-8")

    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "run_codex.ps1"),
            "-BriefFile",
            str(brief),
            "-Repo",
            str(repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    canonical_result = repo / ".ai" / "codex_task_v090_ps_audit.txt.result.json"
    assert canonical_result.exists(), f"canonical result.json missing: {canonical_result}"
    result = json.loads(canonical_result.read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"


# --- stdin closure tests (added 2026-07-09) ---
#
# SKILL.md and references/wrapper.md promise the wrappers close codex's stdin
# (upstream issue #20919: codex exec blocks forever reading an inherited open
# stdin; 25-minute zero-byte hang on 2026-05-14). Each test feeds data on the
# WRAPPER's stdin while a fake codex echoes back whatever it reads from its
# own stdin. If the wrapper leaks its stdin to codex, the marker string shows
# up in the log and the test fails.


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_run_codex_sh_closes_codex_stdin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "DATA=$(cat)\n"
        'printf "stdin:[%s]\\n" "$DATA"\n',
        encoding="utf-8",
        newline="\n",
    )
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
        input="LEAKED_PARENT_STDIN\n",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    log = log_file.read_text(encoding="utf-8")
    assert "stdin:[]" in log, f"codex read a non-empty stdin: {log!r}"
    assert "LEAKED_PARENT_STDIN" not in log


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
@pytest.mark.skipif(shutil.which("python") is None, reason="python not on PATH (fake codex needs it)")
def test_run_codex_ps1_closes_codex_stdin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text(
        "@echo off\r\n"
        "python -c \"import sys; print('stdin:[' + sys.stdin.read().strip() + ']')\"\r\n",
        encoding="utf-8",
    )

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
        input="LEAKED_PARENT_STDIN\r\n",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    log = log_file.read_text(encoding="utf-8-sig")
    assert "stdin:[]" in log, f"codex read a non-empty stdin: {log!r}"
    assert "LEAKED_PARENT_STDIN" not in log


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
def test_run_codex_ps1_inline_guard_fires(tmp_path: Path) -> None:
    """PowerShell parity: inline -Prompt > 500 chars with no brief is refused."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text("@echo off\r\necho should-not-run\r\n", encoding="utf-8")

    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)
    # ensure escape hatch is NOT set
    env.pop("CODEX_DELEGATE_ALLOW_INLINE", None)

    long_prompt = "x" * 600
    proc = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "run_codex.ps1"),
            "-Prompt",
            long_prompt,
            "-Repo",
            str(repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}; stderr={proc.stderr}"
    assert "brief must be on disk" in proc.stderr


@pytest.mark.skipif(_BASH is None, reason="bash (git-bash on Windows, system bash elsewhere) not available")
def test_run_codex_sh_new_usage_limit_message_maps_to_fallback(tmp_path: Path) -> None:
    """codex-cli 0.144.x quota message maps to status=fallback, not error.

    Observed live 2026-07-21 (codex-cli 0.144.1): the CLI now says
    "ERROR: You've hit your usage limit. Upgrade to Pro (...) ... or try
    again at Jul 25th, 2026 12:03 AM." and exits 1. None of the older
    quota patterns (quota exceeded / rate limit / 429 / ...) match it, so
    the wrapper misreported a plain hard error and skipped the
    .fallback_claude sentinel the supervising agent keys on.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex_quota.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "echo \"ERROR: You've hit your usage limit. Upgrade to Pro"
        " (https://chatgpt.com/explore/pro), visit"
        " https://chatgpt.com/codex/settings/usage to purchase more credits"
        " or try again at Jul 25th, 2026 12:03 AM.\" >&2\n"
        "exit 1\n",
        encoding="utf-8",
        newline="\n",
    )
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    log_file = repo / ".ai" / "codex_log.txt"
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
        check=False,
    )

    result_path = log_file.with_suffix(log_file.suffix + ".result.json")
    assert result_path.exists(), f"no result.json written; stderr={proc.stderr}"
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    assert result["status"] == "fallback", (
        f"new usage-limit message must map to fallback, got {result['status']!r}"
    )
    assert (repo / ".ai" / "codex_log.txt.fallback_claude").exists(), (
        "fallback sentinel missing - supervising agent cannot detect quota"
    )


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
def test_run_codex_ps1_new_usage_limit_message_maps_to_fallback(tmp_path: Path) -> None:
    """PowerShell parity for the codex-cli 0.144.x usage-limit wording."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text(
        "@echo off\r\n"
        "echo ERROR: You've hit your usage limit. Upgrade to Pro or visit"
        " settings to purchase more credits or try again at Jul 25th. 1>&2\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
    )

    log_file = repo / ".ai" / "codex_log.txt"
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

    result_path = log_file.with_suffix(log_file.suffix + ".result.json")
    assert result_path.exists(), f"no result.json written; stderr={proc.stderr}"
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    assert result["status"] == "fallback", (
        f"new usage-limit message must map to fallback, got {result['status']!r}"
    )
    assert (repo / ".ai" / "codex_log.txt.fallback_claude").exists()


@pytest.mark.skipif(_BASH is None, reason="bash (git-bash on Windows, system bash elsewhere) not available")
def test_run_codex_sh_exit0_with_quota_phrase_stays_success(tmp_path: Path) -> None:
    """A SUCCESSFUL run whose output merely contains a quota-like phrase
    must stay status=success — the quota classifier only runs on failure.

    False-positive direction: without exit-code gating, a legitimate task
    (e.g. building an in-app-purchase feature) that echoes "purchase more
    credits" in its transcript would be silently reclassified as fallback
    and its good diff discarded.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex_ok.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'implemented the store page: users can purchase more credits'\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    if sys.platform != "win32":
        os.chmod(fake_codex, 0o755)

    log_file = repo / ".ai" / "codex_log.txt"
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
        check=False,
    )

    result_path = log_file.with_suffix(log_file.suffix + ".result.json")
    assert result_path.exists(), f"no result.json written; stderr={proc.stderr}"
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    assert result["status"] == "success", (
        f"exit-0 run with incidental quota phrase must stay success, got {result['status']!r}"
    )
    assert not (repo / ".ai" / "codex_log.txt.fallback_claude").exists()


@pytest.mark.skipif(shutil.which("powershell") is None, reason="powershell not on PATH")
def test_run_codex_ps1_exit0_with_quota_phrase_stays_success(tmp_path: Path) -> None:
    """PowerShell parity: exit-0 output with an incidental quota phrase
    stays status=success (Test-QuotaError is gated on failure)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text(
        "@echo off\r\n"
        "echo implemented the store page: users can purchase more credits\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )

    log_file = repo / ".ai" / "codex_log.txt"
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

    result_path = log_file.with_suffix(log_file.suffix + ".result.json")
    assert result_path.exists(), f"no result.json written; stderr={proc.stderr}"
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    assert result["status"] == "success", (
        f"exit-0 run with incidental quota phrase must stay success, got {result['status']!r}"
    )
    assert not (repo / ".ai" / "codex_log.txt.fallback_claude").exists()
