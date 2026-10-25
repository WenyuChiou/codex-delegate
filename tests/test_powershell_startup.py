"""Startup policy checks use command doubles, never a model invocation."""
import subprocess

import pytest

from powershell_startup import prepare_powershell


def test_startup_loads_required_module_with_a_separate_deadline():
    calls = []
    expected = subprocess.CompletedProcess([], 0, '', '')

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return expected

    assert prepare_powershell('shell with spaces/pwsh', run=runner) is expected
    assert len(calls) == 1
    args, options = calls[0]
    assert args[:5] == ['shell with spaces/pwsh', '-NoLogo', '-NoProfile',
                        '-NonInteractive', '-Command']
    assert 'Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop' in args[5]
    assert 'Get-Command Get-FileHash -ErrorAction Stop' in args[5]
    assert options == dict(capture_output=True, text=True, check=True, timeout=60)


def test_absent_shell_does_not_launch_or_claim_a_successful_probe():
    def forbidden(*args, **kwargs):
        pytest.fail('No shell is available to launch')

    assert prepare_powershell(None, run=forbidden) is None


@pytest.mark.parametrize('error', [
    subprocess.TimeoutExpired(['pwsh'], 60),
    subprocess.CalledProcessError(1, ['pwsh'], stderr='module unavailable'),
    FileNotFoundError('shell disappeared'),
])
def test_startup_errors_propagate_without_retry_or_skip(error):
    calls = []

    def runner(*args, **kwargs):
        calls.append(1)
        raise error

    with pytest.raises(type(error)) as caught:
        prepare_powershell('pwsh', run=runner)
    assert caught.value is error
    assert calls == [1]
