"""Bounded, model-free shell startup for the process regression suite."""
import subprocess


def prepare_powershell(executable, *, run=None):
    """Load required modules once before applying the short per-case deadline.

    Hosted runners can spend longer than 15 seconds starting the first .NET
    process. A separate 60-second probe exposes startup/module failures without
    weakening the wrapper tests' own 15-second execution timeout or assertions.
    Missing shells remain subject to the existing per-test availability skips.
    """
    if executable is None:
        return None
    runner = subprocess.run if run is None else run
    return runner(
        [executable, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command',
         'Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop; '
         '$null = Get-Command Get-FileHash -ErrorAction Stop'],
        capture_output=True, text=True, check=True, timeout=60,
    )
