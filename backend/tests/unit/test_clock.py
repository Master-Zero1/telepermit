"""Unit tests for Clock and TickClock (CONTRACTS section 5, task 1.1)."""

from __future__ import annotations

import math

import pytest

from telepermit.clock import TICK_S, TickClock


def test_start_value_and_now() -> None:
    assert TickClock().now() == 0.0
    assert TickClock(5.5).now() == 5.5
    assert TickClock(start=2.0).now() == 2.0


def test_advance_by_one() -> None:
    clock = TickClock(0.0)
    clock.advance(1.0)
    assert clock.now() == 1.0


def test_advance_zero_allowed() -> None:
    clock = TickClock(3.0)
    clock.advance(0)
    assert clock.now() == 3.0


def test_advance_negative_raises() -> None:
    """Time never goes backwards (security invariant 8)."""
    clock = TickClock(3.0)
    with pytest.raises(ValueError):
        clock.advance(-0.001)
    assert clock.now() == 3.0


@pytest.mark.parametrize("dt", [math.nan, math.inf, -math.inf])
def test_advance_nan_and_infinity_raise(dt: float) -> None:
    clock = TickClock(3.0)
    with pytest.raises(ValueError):
        clock.advance(dt)
    assert clock.now() == 3.0


@pytest.mark.parametrize("start", [math.nan, math.inf, -math.inf])
def test_non_finite_start_raises(start: float) -> None:
    with pytest.raises(ValueError):
        TickClock(start)


def test_thirty_ticks_equal_thirty() -> None:
    clock = TickClock(0.0)
    for _ in range(30):
        clock.advance(TICK_S)
    assert clock.now() == 30.0


def test_tick_s_is_one() -> None:
    assert TICK_S == 1.0
