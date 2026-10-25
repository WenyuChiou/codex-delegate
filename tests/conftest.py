"""Keep shell startup separate from each deterministic wrapper invocation."""
import pytest

from powershell_startup import prepare_powershell
from test_wrappers import _resolve_powershell


@pytest.fixture(scope='session', autouse=True)
def powershell_startup():
    # Fail on startup/module errors; never turn them into skips or retries.
    prepare_powershell(_resolve_powershell())
