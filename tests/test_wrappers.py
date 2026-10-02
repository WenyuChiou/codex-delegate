"""Wrapper contract tests.

Bash test:
- Linux / macOS: `bash` from PATH, POSIX paths.
- Windows: explicitly use git-bash at `C:\\Program Files\\Git\\bin\\bash.exe`
  if present. Avoids WSL bash on PATH which (when no distro is installed,
  e.g. on GitHub Actions windows-latest) emits UTF-16 banner output that
  pollutes subprocess pipes. Skipif when git-bash isn't found so plain
  Windows hosts without Git for Windows skip cleanly instead of failing.

PowerShell tests:
- Use pwsh or Windows PowerShell when installed. Native delegate doubles
  use the host shell; Linux pwsh passes do not certify native Windows behavior.
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


def _resolve_powershell(platform=None, which=None):
    """Retain the original Windows PowerShell gate, add Core elsewhere."""
    platform = sys.platform if platform is None else platform
    which = shutil.which if which is None else which
    names = ("powershell", "pwsh") if platform == "win32" else ("pwsh", "powershell")
    return next((path for name in names if (path := which(name))), None)


_POWERSHELL = _resolve_powershell()


def _fake_ps_delegate(tmp_path: Path, *, output="delegate ok", edit=False,
                      read_stdin=False, show_args=False, returncode=0) -> Path:
    """Native command double; the real PowerShell wrapper still executes."""
    if sys.platform == "win32":
        fake = tmp_path / "codex.cmd"
        body = "@echo off\r\n"
        if edit:
            body += 'echo delegated content>"%~5\\delegated_file.txt"\r\n'
        if read_stdin:
            body += "python -c \"import sys; print('stdin:[' + sys.stdin.read().strip() + ']')\"\r\n"
        else:
            body += "echo " + ("%*" if show_args else output) + "\r\n"
        body += f"exit /b {returncode}\r\n"
    else:
        import shlex
        fake = tmp_path / "codex.sh"
        body = "#!/usr/bin/env bash\n"
        if edit:
            body += 'printf "delegated content\\n" > "$5/delegated_file.txt"\n'
        if read_stdin:
            body += "python -c \"import sys; print('stdin:[' + sys.stdin.read().strip() + ']')\"\n"
        elif show_args:
            body += 'printf "%s\\n" "$*"\n'
        else:
            body += "printf '%s\\n' " + shlex.quote(output) + "\n"
        body += f"exit {returncode}\n"
    fake.write_text(body, encoding="utf-8")
    if sys.platform != "win32":
        fake.chmod(0o755)
    return fake

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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_run_codex_ps1_reports_files_changed(tmp_path: Path) -> None:
    """PowerShell wrapper: files_changed is auto-derived from git porcelain."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    # Fake codex writes a file into the repo. %~5 is the `-C <repo>` value.
    fake_codex = _fake_ps_delegate(tmp_path, edit=True)

    log_file = repo / ".ai" / "codex_ps_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
def test_run_codex_ps1_files_changed_empty_when_not_git(tmp_path: Path) -> None:
    """PS wrapper: files_changed degrades to [] when the repo is not a git work tree."""
    repo = tmp_path / "repo"
    repo.mkdir()  # deliberately NOT a git repo

    fake_codex = _fake_ps_delegate(tmp_path, edit=True)

    log_file = repo / ".ai" / "codex_ps_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
def test_run_codex_ps1_writes_result_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = _fake_ps_delegate(tmp_path)

    log_file = repo / ".ai" / "codex_ps_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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

def _run_sh(repo: Path, fake_codex: Path, extra_args: list[str], env_extra: dict[str, str] | None = None, *, cwd: Path | None = None, wrapper: Path | None = None):
    wrapper = wrapper or ROOT / "scripts" / "run_codex.sh"
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
                + f"'{to_bash_path(Path(_BASH))}' '{to_bash_path(wrapper)}' "
                f"--repo '{to_bash_path(repo)}' {cmd_args}"
            ),
        ],
        cwd=cwd,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
def test_run_codex_ps1_brief_file_canonical_path(tmp_path: Path) -> None:
    """PowerShell parity: -BriefFile auto-derives log path next to brief."""
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    brief = repo / ".ai" / "codex_task_v090_ps_audit.md"
    brief.write_text("# Brief\nDo X.\n", encoding="utf-8")

    fake_codex = _fake_ps_delegate(tmp_path)

    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
@pytest.mark.skipif(shutil.which("python") is None, reason="python not on PATH (fake codex needs it)")
def test_run_codex_ps1_closes_codex_stdin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = _fake_ps_delegate(tmp_path, read_stdin=True)

    log_file = repo / ".ai" / "codex_ps_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
def test_run_codex_ps1_inline_guard_fires(tmp_path: Path) -> None:
    """PowerShell parity: inline -Prompt > 500 chars with no brief is refused."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = _fake_ps_delegate(tmp_path, output="should-not-run")

    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)
    # ensure escape hatch is NOT set
    env.pop("CODEX_DELEGATE_ALLOW_INLINE", None)

    long_prompt = "x" * 600
    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
def test_run_codex_ps1_new_usage_limit_message_maps_to_fallback(tmp_path: Path) -> None:
    """PowerShell parity for the codex-cli 0.144.x usage-limit wording."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = _fake_ps_delegate(tmp_path, output="ERROR: You've hit your usage limit. Upgrade to Pro or visit settings to purchase more credits or try again at Jul 25th.", returncode=1)

    log_file = repo / ".ai" / "codex_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
def test_run_codex_ps1_exit0_with_quota_phrase_stays_success(tmp_path: Path) -> None:
    """PowerShell parity: exit-0 output with an incidental quota phrase
    stays status=success (Test-QuotaError is gated on failure)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = _fake_ps_delegate(tmp_path, output="implemented the store page: users can purchase more credits")

    log_file = repo / ".ai" / "codex_log.txt"
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)

    proc = subprocess.run(
        [
            _POWERSHELL,
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


@pytest.mark.skipif(_BASH is None, reason="bash not available")
@pytest.mark.parametrize("brief_location", ["caller", "repo"])
def test_relative_brief_resolves_before_codex_changes_cwd(tmp_path: Path, brief_location: str) -> None:
    """The accepted brief and derived log must refer to the same physical file."""
    repo = tmp_path / "repo with spaces"
    caller = tmp_path / "caller"
    repo.mkdir()
    caller.mkdir()
    owner = caller if brief_location == "caller" else repo
    (owner / ".ai").mkdir()
    brief = owner / ".ai" / "codex_task_contract.md"
    brief.write_text("# Synthetic brief\nApply the stated mechanical edit.\n", encoding="utf-8")

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        'cd "$5" || exit 90\n'
        'prompt="${!#}"\n'
        'brief="${prompt#Read }"\n'
        'brief="${brief% and execute all instructions inside.}"\n'
        '[[ -f "$brief" ]] || { echo "brief inaccessible from Codex cwd" >&2; exit 91; }\n'
        'printf "brief:[%s]\\n" "$brief"\n',
        encoding="utf-8", newline="\n",
    )
    proc = _run_sh(repo, fake_codex, ["--brief-file", ".ai/codex_task_contract.md"], cwd=caller)
    assert proc.returncode == 0, proc.stderr
    log = brief.with_suffix(".txt")
    assert log.is_file(), "results must stay beside the accepted brief"
    assert f"brief:[{to_bash_path(brief)}]" in log.read_text(encoding="utf-8")
    result = json.loads(Path(str(log) + ".result.json").read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"


@pytest.mark.skipif(_BASH is None, reason="bash not available")
def test_portable_skill_bash_wrapper_runs_without_repository_root(tmp_path: Path) -> None:
    """Copy just the skill directory, as portable skill hosts do."""
    installed = tmp_path / "isolated_skill"
    shutil.copytree(ROOT / "skills" / "codex-delegate", installed)
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    brief = repo / ".ai" / "codex_task_packaged.md"
    brief.write_text("# Synthetic brief\nApply the stated mechanical edit.\n", encoding="utf-8")
    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n", encoding="utf-8", newline="\n")
    proc = _run_sh(repo, fake_codex, ["--brief-file", to_bash_path(brief), "--model", "synthetic-model"],
                   wrapper=installed / "scripts" / "run_codex.sh")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(brief.with_suffix(".txt.result.json").read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"
    assert result["model"] == "codex/synthetic-model"
    log = brief.with_suffix(".txt").read_text(encoding="utf-8")
    assert "workspace-write" in log and to_bash_path(repo) in log


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
@pytest.mark.parametrize("brief_location", ["caller", "repo"])
def test_relative_brief_ps1_resolves_before_codex_changes_cwd(tmp_path: Path, brief_location: str) -> None:
    """Windows parity for caller-first lookup and absolute prompt/log paths."""
    repo = tmp_path / "repo with spaces"
    caller = tmp_path / "caller"
    repo.mkdir()
    caller.mkdir()
    owner = caller if brief_location == "caller" else repo
    (owner / ".ai").mkdir()
    brief = owner / ".ai/codex_task_contract.md"
    brief.write_text("# Synthetic brief\nApply the stated mechanical edit.\n", encoding="utf-8")
    fake_codex = _fake_ps_delegate(tmp_path, show_args=True)
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake_codex)
    env.pop("CODEX_DELEGATE_ALLOW_INLINE", None)
    proc = subprocess.run(
        [_POWERSHELL, "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/run_codex.ps1"),
         "-BriefFile", str(Path(".ai/codex_task_contract.md")), "-Repo", str(repo)],
        cwd=caller, capture_output=True, text=True, env=env, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    log = brief.with_suffix(".txt")
    assert log.is_file(), "results must stay beside the accepted brief"
    assert str(brief) in log.read_text(encoding="utf-8-sig")
    result = json.loads(Path(str(log) + ".result.json").read_text(encoding="utf-8-sig"))
    assert result["status"] == "success"


@pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell runtime not on PATH")
@pytest.mark.parametrize("wrapper_path", ["scripts/run_codex.ps1", "skills/codex-delegate/scripts/run_codex.ps1"])
@pytest.mark.parametrize("status, delegate_code, output", [
    ("success", 0, "delegate ok"),
    ("error", 7, "synthetic delegate failure"),
    ("fallback", 1, "ERROR: You've hit your usage limit"),
])
def test_default_powershell_log_and_result_stay_inside_repo(tmp_path: Path, status, delegate_code, output, wrapper_path):
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    fake = _fake_ps_delegate(tmp_path, output=output, returncode=delegate_code)
    env = os.environ.copy()
    env["CODEX_PATH"] = str(fake)
    proc = subprocess.run([_POWERSHELL, "-NoLogo", "-NoProfile", "-File",
                           str(ROOT / wrapper_path), "-Prompt", "do work",
                           "-Repo", str(repo)], capture_output=True, text=True, env=env)
    log = repo / ".ai/codex_output.txt"
    result_path = Path(str(log) + ".result.json")
    assert result_path.is_file(), (proc.returncode, proc.stderr, list(tmp_path.iterdir()))
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    assert result["status"] == status
    assert result["log_file"] == str(log)
    if status != "error":
        assert log.is_file()
    assert not list(tmp_path.glob("repo with spaces*result.json"))
    sentinel = ".fallback_claude" if status == "fallback" else ".done" if status == "success" else ".error"
    assert Path(str(log) + sentinel).is_file()


@pytest.mark.parametrize("platform, available, expected", [
    ("win32", {"powershell": "legacy", "pwsh": "core"}, "legacy"),
    ("linux", {"powershell": "legacy", "pwsh": "core"}, "core"),
    ("win32", {"pwsh": "core"}, "core"),
    ("linux", {"powershell": "legacy"}, "legacy"),
    ("win32", {}, None),
])
def test_powershell_resolver_preserves_windows_gate(platform, available, expected):
    assert _resolve_powershell(platform, available.get) == expected
