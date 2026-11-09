"""Unit tests for the driver types (CONTRACTS section 7, task 3.1)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from telepermit.drivers.base import AgentDriver, Observation, Proposal

BASE_PATH = Path(__file__).resolve().parents[2] / "src" / "telepermit" / "drivers" / "base.py"


def make_observation(last_result: str | None = None) -> Observation:
    return Observation(
        task="Summarise the briefing.",
        turn=1,
        place="library",
        tools=[{"name": "finish", "description": "End the run.", "args": {}}],
        last_result=last_result,
    )


def test_proposal_and_observation_are_frozen() -> None:
    proposal = Proposal("finish", {})
    observation = make_observation()
    with pytest.raises(dataclasses.FrozenInstanceError):
        proposal.action = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.turn = 2  # type: ignore[misc]


def test_proposal_fields() -> None:
    proposal = Proposal("read_document", {"name": "briefing-q3"})
    assert proposal.action == "read_document"
    assert proposal.args == {"name": "briefing-q3"}
    assert {f.name for f in dataclasses.fields(Proposal)} == {"action", "args"}


def test_observation_field_set_exactly_five() -> None:
    """Security invariant 9: no permit, spend, cost, step count or key can be added by accident."""
    names = {f.name for f in dataclasses.fields(Observation)}
    assert names == {"task", "turn", "place", "tools", "last_result"}


def test_base_imports_no_telepermit_modules() -> None:
    """Security invariant 2: the driver types import nothing from the runtime."""
    tree = ast.parse(BASE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != "telepermit", alias.name
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import at line {node.lineno}"
            assert (node.module or "").split(".")[0] != "telepermit", node.module


class ConstantDriver:
    """A driver that always proposes the same action."""

    def propose(self, observation: Observation) -> Proposal:
        return Proposal("finish", {})


def ask(driver: AgentDriver, observation: Observation) -> Proposal:
    return driver.propose(observation)


def test_structural_agent_driver() -> None:
    result = ask(ConstantDriver(), make_observation())
    assert result == Proposal("finish", {})
