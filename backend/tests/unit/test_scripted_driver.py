"""Unit tests for ScriptedDriver (CONTRACTS section 7, task 1.1)."""

from __future__ import annotations

from telepermit import drivers, engine
from telepermit.drivers.base import Observation, Proposal
from telepermit.drivers.scripted import ScriptedDriver

SCRIPT = [
    Proposal("read_document", {"name": "briefing-q3"}),
    Proposal("go:vault", {}),
    Proposal("read_records", {}),
]


def observation(turn: int = 1) -> Observation:
    return Observation(task="a task", turn=turn, place="library", tools=[], last_result=None)


def test_returns_script_in_order() -> None:
    """Requirement 4.1: the scripted proposals come back in order."""
    driver = ScriptedDriver(SCRIPT)
    assert [driver.propose(observation(turn)) for turn in (1, 2, 3)] == SCRIPT


def test_repeats_last_when_enabled() -> None:
    """Requirement 4.1: with repeat_last (the default) the last proposal repeats forever."""
    for driver in (ScriptedDriver(SCRIPT), ScriptedDriver(SCRIPT, repeat_last=True)):
        for turn in (1, 2, 3):
            driver.propose(observation(turn))
        later = [driver.propose(observation(turn)) for turn in range(4, 10)]
        assert later == [SCRIPT[-1]] * 6


def test_exhausted_without_repeat_proposes_finish() -> None:
    """Decision (e): an exhausted script without repeat_last proposes finish."""
    driver = ScriptedDriver(SCRIPT, repeat_last=False)
    assert [driver.propose(observation(turn)) for turn in (1, 2, 3)] == SCRIPT
    later = [driver.propose(observation(turn)) for turn in range(4, 8)]
    assert later == [Proposal("finish", {})] * 4


def test_empty_script_proposes_finish() -> None:
    """Decision (e): an empty script proposes finish, whatever repeat_last says."""
    for repeat_last in (True, False):
        driver = ScriptedDriver([], repeat_last=repeat_last)
        assert [driver.propose(observation(turn)) for turn in (1, 2, 3)] == [
            Proposal("finish", {})
        ] * 3


def test_observation_is_ignored() -> None:
    first = ScriptedDriver(SCRIPT)
    second = ScriptedDriver(SCRIPT)
    other = Observation(task="other", turn=9, place="vault", tools=[], last_result="x")
    for turn in range(1, 6):
        assert first.propose(observation(turn)) == second.propose(other)


def test_script_is_copied() -> None:
    """The driver keeps its own copy of the script and of every args dict."""
    script = [Proposal("read_document", {"name": "briefing-q3"})]
    driver = ScriptedDriver(script)
    script.append(Proposal("finish", {}))
    script[0].args["name"] = "changed"
    first = driver.propose(observation(1))
    assert first == Proposal("read_document", {"name": "briefing-q3"})
    first.args["name"] = "changed again"
    second = driver.propose(observation(2))
    assert second == Proposal("read_document", {"name": "briefing-q3"})


def test_label_is_scripted() -> None:
    assert ScriptedDriver.label == "scripted"
    assert ScriptedDriver(SCRIPT).label == "scripted"


def test_protocol_literals_match_engine() -> None:
    """The driver literals equal the engine ones (drivers cannot import the engine)."""
    assert drivers.FINISH_ACTION == engine.FINISH_ACTION == "finish"
    assert drivers.GO_PREFIX == engine.GO_PREFIX == "go:"
