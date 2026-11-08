"""Unit tests for Permit construction and validation (CONTRACTS section 2, task 1.1)."""

from __future__ import annotations

import dataclasses
import math

import pytest

from telepermit.permit import Permit


def make(**overrides: object) -> Permit:
    fields: dict[str, object] = {
        "lifetime_s": 60.0,
        "max_steps": 30,
        "allowance": 60,
        "allowed_actions": frozenset({"read_document"}),
    }
    fields.update(overrides)
    return Permit(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field, value",
    [
        ("lifetime_s", -1.0),
        ("lifetime_s", -0.001),
        ("max_steps", -1),
        ("allowance", -1),
    ],
)
def test_negative_values_raise_value_error(field: str, value: float) -> None:
    """Requirement 1.1: a negative limit raises ValueError."""
    with pytest.raises(ValueError):
        make(**{field: value})


def test_zero_limits_and_empty_actions_valid() -> None:
    """Requirement 1.1: zero is valid and allowed_actions may be empty."""
    p = Permit(lifetime_s=0, max_steps=0, allowance=0, allowed_actions=frozenset())
    assert p.lifetime_s == 0.0
    assert p.max_steps == 0
    assert p.allowance == 0
    assert p.allowed_actions == frozenset()
    assert Permit(0.0, 0, 0, []).allowed_actions == frozenset()


def test_int_lifetime_is_coerced_to_float() -> None:
    p = make(lifetime_s=5)
    assert isinstance(p.lifetime_s, float)
    assert p == make(lifetime_s=5.0)


@pytest.mark.parametrize("actions", [["a", "b"], {"a", "b"}, ("a", "b"), frozenset({"a", "b"})])
def test_allowed_actions_are_coerced_to_frozenset(actions: object) -> None:
    p = make(allowed_actions=actions)
    assert isinstance(p.allowed_actions, frozenset)
    assert p.allowed_actions == frozenset({"a", "b"})


@pytest.mark.parametrize("field", ["max_steps", "allowance"])
@pytest.mark.parametrize("value", [True, False, 1.0, 2.5])
def test_bool_or_float_for_int_fields_raises_type_error(field: str, value: object) -> None:
    with pytest.raises(TypeError):
        make(**{field: value})


def test_bare_str_for_allowed_actions_raises_type_error() -> None:
    with pytest.raises(TypeError):
        make(allowed_actions="read")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_lifetime_raises_value_error(value: float) -> None:
    with pytest.raises(ValueError):
        make(lifetime_s=value)


def test_permit_is_frozen() -> None:
    p = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.max_steps = 99  # type: ignore[misc]
