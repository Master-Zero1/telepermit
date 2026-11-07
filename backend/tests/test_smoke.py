from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

import telepermit


def test_package_version() -> None:
    assert telepermit.__version__ == "0.1.0"


@given(st.integers())
def test_hypothesis_runs(n: int) -> None:
    """Smoke check that Hypothesis runs. Not a permit property test, so no P-id yet."""
    assert int(str(n)) == n
