"""Adversarial process regressions; all delegate outputs are deterministic doubles."""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
import pytest
from test_wrappers import _resolve_bash, _resolve_powershell, to_bash_path

ROOT = Path(__file__).resolve().parents[1]
BASH = _resolve_bash()
PWSH = _resolve_powershell()

def git(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)

def invoke(tmp_path, shell, *, action='edit', output='fixture ok', code=0, sandbox=None, dirty=True, staged=False, filename='calc.py', tracked=True, dualcase=False):
    repo = tmp_path / 'repo'; repo.mkdir()
    target = repo / filename
    target.write_bytes(b'baseline\x00\xff\n')
    if dualcase: (repo / 'case.py').write_bytes(b'baseline lower case\n')
    (repo / 'baseline.md').write_text('fixture baseline\n', encoding='utf-8')
    git(repo, 'init', '-q'); git(repo, 'add', '.' if tracked else 'baseline.md')
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'baseline')
    if dirty:
        target.write_bytes(b'pre-existing dirty\x00\xff\n')
        if dualcase: (repo / 'case.py').write_bytes(b'pre-existing lower dirty\n')
        if staged: git(repo, 'add', filename)
    fake = tmp_path / 'codex.sh'
    # Native host shell executes this fixture; no Codex or paid inference.
    if os.name == 'nt' and shell == 'powershell':
        fake = tmp_path / 'codex.cmd'
        fake.write_text('@echo off\r\npython "%~dp0delegate.py" %*\r\nexit /b %errorlevel%\r\n', encoding='utf-8', newline='\n')
    else:
        python_command = 'python' if os.name == 'nt' else 'python3'
        fake.write_text(f'#!/usr/bin/env bash\nexec {python_command} "$(dirname "$0")/delegate.py" "$@"\n', encoding='utf-8', newline='\n')
        fake.chmod(0o755)
    delegate = tmp_path / 'delegate.py'
    delegate.write_text('import json,sys\nfrom pathlib import Path\n' +
        f'path=Path({str(target)!r})\naction={action!r}\n' +
        "if action == 'edit': path.write_bytes(b'delegated new content\\x00\\xfe\\n')\n" +
        "elif action == 'delete': path.unlink()\n" +
        "elif action == 'revert': path.write_bytes(b'baseline\\x00\\xff\\n')\n" +
        "elif action == 'rename': path.rename(path.with_name('renamed.bin'))\n" +
        "elif action == 'stage': __import__('subprocess').run(['git', '-C', str(path.parent), 'add', path.name], check=True)\n" +
        f"if {dualcase!r}: (path.parent / 'case.py').write_bytes(b'delegated lower new content\\n')\n" +
        f"Path({str(tmp_path / 'args.json')!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\nprint({output!r})\nsys.exit({code})\n", encoding='utf-8', newline='\n')
    log = tmp_path / 'run.log'
    env = os.environ.copy(); env['CODEX_PATH'] = to_bash_path(fake) if shell == 'bash' else str(fake)
    if shell == 'bash':
        if not BASH: pytest.skip('Bash unavailable')
        cmd = [BASH, to_bash_path(ROOT / 'scripts/run_codex.sh'), '--repo', to_bash_path(repo), '--prompt', 'fixture', '--log-file', to_bash_path(log)]
        if sandbox: cmd += ['--sandbox', sandbox]
    else:
        if not PWSH: pytest.skip('PowerShell unavailable')
        cmd = [PWSH, '-NoProfile', '-File', str(ROOT / 'scripts/run_codex.ps1'), '-Repo', str(repo), '-Prompt', 'fixture', '-LogFile', str(log)]
        if sandbox: cmd += ['-Sandbox', sandbox]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)
    result = json.loads(Path(str(log) + '.result.json').read_text(encoding='utf-8-sig')) if Path(str(log) + '.result.json').exists() else None
    return p, result, repo, tmp_path / 'args.json'

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
@pytest.mark.parametrize('action,staged,expected', [
    ('edit', False, ['calc.py']), ('edit', True, ['calc.py']),
    ('delete', False, ['calc.py']), ('revert', False, ['calc.py']),
    ('noop', False, []), ('noop', True, []),
    ('rename', False, ['calc.py', 'renamed.bin']),
    ('stage', False, ['calc.py']),
])
def test_dirty_content_attribution(tmp_path, shell, action, staged, expected):
    p, result, _, _ = invoke(tmp_path, shell, action=action, staged=staged)
    assert p.returncode == 0, p.stderr
    assert result['files_changed'] == expected

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
def test_dirty_edit_on_failure_is_reported(tmp_path, shell):
    p, result, _, _ = invoke(tmp_path, shell, output='compiler unavailable', code=7)
    assert p.returncode == 1
    assert result['status'] == 'error'
    assert result['files_changed'] == ['calc.py']

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
@pytest.mark.parametrize('action,expected', [('edit', ['calc.py']), ('delete', ['calc.py']), ('noop', [])])
def test_preexisting_untracked_content(tmp_path, shell, action, expected):
    p, result, _, _ = invoke(tmp_path, shell, action=action, tracked=False)
    assert p.returncode == 0, p.stderr
    assert result['files_changed'] == expected

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
def test_case_distinct_dirty_paths(tmp_path, shell):
    probe = tmp_path / 'case-probe'; probe.mkdir()
    upper, lower = probe / 'Case', probe / 'case'
    upper.write_text('upper', encoding='utf-8'); lower.write_text('lower', encoding='utf-8')
    if os.path.samefile(upper, lower): pytest.skip('Filesystem cannot hold case-distinct paths')
    p, result, _, _ = invoke(tmp_path, shell, filename='Case.py', dualcase=True)
    assert p.returncode == 0, p.stderr
    assert result['files_changed'] == ['Case.py', 'case.py']

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
@pytest.mark.parametrize('filename', ['quoted "file".bin', 'name -> arrow.bin', 'spaced file.bin', 'unicode-測試.bin'])
def test_filename_identity(tmp_path, shell, filename):
    if os.name == 'nt' and '"' in filename: pytest.skip('Windows forbids double quotes in filenames')
    p, result, _, _ = invoke(tmp_path, shell, filename=filename)
    assert p.returncode == 0, p.stderr
    assert result['files_changed'] == [filename]

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
@pytest.mark.parametrize('output,code,status', [
    ('Fixture rejection at source line 429: invalid syntax', 7, 'error'),
    ('Unexpected HTTP status 429 Too Many Requests', 7, 'fallback'),
    ('HTTP/1.1 429 Too Many Requests', 7, 'fallback'),
    ('Request failed with status_code=429', 7, 'fallback'),
    ('status 4290 is unrelated', 7, 'error'),
    ('HTTP 429 mentioned in generated documentation', 0, 'success'),
    ('Rate limit exceeded', 7, 'fallback'),
])
def test_quota_context(tmp_path, shell, output, code, status):
    p, result, _, _ = invoke(tmp_path, shell, output=output, code=code, action='noop')
    assert p.returncode == (1 if status == 'error' else 0), p.stderr
    assert result['status'] == status

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
def test_read_only_is_forwarded(tmp_path, shell):
    p, result, _, args_path = invoke(tmp_path, shell, action='noop', sandbox='read-only')
    assert p.returncode == 0, p.stderr
    args = json.loads(args_path.read_text(encoding='utf-8'))
    assert args[args.index('--sandbox') + 1] == 'read-only'
    assert result['files_changed'] == []

def test_powershell_normalizes_sandbox_case(tmp_path):
    p, _, _, args_path = invoke(tmp_path, 'powershell', action='noop', sandbox='READ-only')
    assert p.returncode == 0, p.stderr
    args = json.loads(args_path.read_text(encoding='utf-8'))
    assert args[args.index('--sandbox') + 1] == 'read-only'

def test_fixture_text_io_is_explicit_utf8(tmp_path, monkeypatch):
    original_write, original_read = Path.write_text, Path.read_text
    def checked_write(path, data, *args, **kwargs):
        assert kwargs.get('encoding') == 'utf-8', 'Fixture write must not inherit Windows locale encoding'
        return original_write(path, data, *args, **kwargs)
    def checked_read(path, *args, **kwargs):
        assert kwargs.get('encoding') in {'utf-8', 'utf-8-sig'}, 'Fixture read must not inherit locale encoding'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', checked_write)
    monkeypatch.setattr(Path, 'read_text', checked_read)
    p, result, _, _ = invoke(tmp_path, 'bash', filename='unicode-測試.bin', dirty=False)
    assert p.returncode == 0, p.stderr
    assert result['status'] == 'success'

@pytest.mark.parametrize('shell', ['bash', 'powershell'])
def test_invalid_sandbox_stops_before_delegate(tmp_path, shell):
    p, result, _, args_path = invoke(tmp_path, shell, sandbox='danger-full-access')
    assert p.returncode != 0
    assert result is None
    assert not args_path.exists()
