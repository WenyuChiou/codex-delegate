import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def to_bash_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


def test_run_codex_sh_writes_result_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text("#!/usr/bin/env bash\necho 'delegate ok'\n", encoding="utf-8", newline="\n")
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
