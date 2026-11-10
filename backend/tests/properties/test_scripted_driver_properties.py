"""Property tests for ScriptedDriver (CONTRACTS section 7)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from telepermit.drivers.base import Observation, Proposal
from telepermit.drivers.scripted import ScriptedDriver

FINISH = Proposal("finish", {})

proposals = st.builds(Proposal, action=st.text(), args=st.dictionaries(st.text(), st.text()))
observations = st.builds(
    Observation,
    task=st.text(max_size=10),
    turn=st.integers(min_value=1, max_value=100),
    place=st.text(max_size=10),
    tools=st.just([]),
    last_result=st.one_of(st.none(), st.text(max_size=10)),
)


def model(script: list[Proposal], repeat_last: bool, calls: int) -> list[Proposal]:
    """The expected proposals: the script, then the last one forever, or finish."""
    expected = []
    for index in range(calls):
        if index < len(script):
            expected.append(script[index])
        elif repeat_last and script:
            expected.append(script[-1])
        else:
            expected.append(FINISH)
    return expected


# Feature: scenario-drivers-replays, Property 1
@given(
    script=st.lists(proposals, max_size=8),
    repeat_last=st.booleans(),
    calls=st.integers(min_value=0, max_value=60),
    first_seen=observations,
    second_seen=observations,
)
def test_p4_1_deterministic_and_follows_script(
    script: list[Proposal],
    repeat_last: bool,
    calls: int,
    first_seen: Observation,
    second_seen: Observation,
) -> None:
    """Property P4.1: a scripted driver is deterministic and follows its script, then repeats the
    last proposal or finishes. Validates: Requirements 4.1"""
    snapshot = [Proposal(item.action, dict(item.args)) for item in script]
    first = ScriptedDriver(script, repeat_last)
    second = ScriptedDriver(script, repeat_last)
    got_first = [first.propose(first_seen) for _ in range(calls)]
    got_second = [second.propose(second_seen) for _ in range(calls)]
    assert got_first == got_second
    assert got_first == model(snapshot, repeat_last, calls)
    assert script == snapshot
