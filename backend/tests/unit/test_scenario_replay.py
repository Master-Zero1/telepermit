"""Unit tests for the replay helpers of the poisoned_briefing scenario (CONTRACTS section 9)."""

from __future__ import annotations

import pytest

from telepermit.audit import permit_json
from telepermit.drivers.base import Observation, Proposal
from telepermit.scenarios.poisoned_briefing import (
    GENERATED_BY_RECORDER,
    HOME_PERMIT,
    LIBRARY_CEILING,
    SCENARIO_NAME,
    TASK,
    VAULT_CEILING,
    replay_identity,
    replay_meta,
    run_scenario,
)
from telepermit.tools import BRIEFING_Q3_TEXT

META_KEYS = {
    "id",
    "title",
    "scenario",
    "driver",
    "enforce",
    "harness_cap",
    "task",
    "home_permit",
    "ceilings",
    "tool_costs",
    "document_text",
    "generated_by",
}
ENFORCED = ("poisoned-briefing-enforced", "Poisoned briefing: limits enforced")
UNENFORCED = ("poisoned-briefing-unenforced", "Poisoned briefing: no enforcement")
FORGED = ("forged-identity-refused", "Forged identity refused at the border")


class Finisher:
    """A driver with a chosen label that finishes at once."""

    def __init__(self, label: str) -> None:
        self.label = label

    def propose(self, observation: Observation) -> Proposal:
        return Proposal("finish", {})


def test_generated_by_recorder_literal() -> None:
    assert GENERATED_BY_RECORDER == "scripts/record_replays.py"


def test_replay_identity_ids_and_titles() -> None:
    """Requirement 4.9: the three scripted replays have the designed ids and titles."""
    assert replay_identity(run_scenario(enforce=True)) == (
        ENFORCED[0],
        f"{ENFORCED[1]} (scripted)",
    )
    assert replay_identity(run_scenario(enforce=False)) == (
        UNENFORCED[0],
        f"{UNENFORCED[1]} (scripted)",
    )
    assert replay_identity(run_scenario(enforce=True, forged=True)) == (
        FORGED[0],
        f"{FORGED[1]} (scripted)",
    )


def test_title_ends_with_label() -> None:
    for kwargs in ({"enforce": True}, {"enforce": False}, {"enforce": True, "forged": True}):
        _, title = replay_identity(run_scenario(**kwargs))  # type: ignore[arg-type]
        assert title.endswith("(scripted)")
        assert "(live LLM)" not in title
    for kwargs in ({"enforce": True}, {"enforce": False}, {"enforce": True, "forged": True}):
        run = run_scenario(driver=Finisher("llm"), **kwargs)  # type: ignore[arg-type]
        _, title = replay_identity(run)
        assert title.endswith("(live LLM)")
        assert "(scripted)" not in title


@pytest.mark.parametrize(
    ("kwargs", "base"),
    [
        ({"enforce": True}, ENFORCED),
        ({"enforce": False}, UNENFORCED),
        ({"enforce": True, "forged": True}, FORGED),
    ],
    ids=["enforced", "unenforced", "forged"],
)
def test_llm_label_gives_suffix_and_title(kwargs: dict[str, bool], base: tuple[str, str]) -> None:
    run = run_scenario(driver=Finisher("llm"), **kwargs)  # type: ignore[arg-type]
    assert replay_identity(run) == (f"{base[0]}-llm", f"{base[1]} (live LLM)")


def test_replay_meta_fields() -> None:
    """Requirement 4.8: the meta has exactly the CONTRACTS section 9 keys."""
    run = run_scenario(enforce=True)
    meta = replay_meta(run, "some-generator")
    assert set(meta) == META_KEYS
    assert (meta["id"], meta["title"]) == replay_identity(run)
    assert meta["scenario"] == SCENARIO_NAME
    assert meta["driver"] == "scripted"
    assert meta["enforce"] is True
    assert meta["harness_cap"] == run.max_turns == 30
    assert meta["task"] == TASK
    assert meta["home_permit"] == permit_json(HOME_PERMIT)
    assert meta["ceilings"] == {
        "library": permit_json(LIBRARY_CEILING),
        "vault": permit_json(VAULT_CEILING),
    }
    assert meta["tool_costs"] == {
        "read_document": 1,
        "search_archive": 5,
        "read_records": 3,
        "export_records": 20,
    }
    assert meta["document_text"] == BRIEFING_Q3_TEXT
    assert meta["generated_by"] == "some-generator"


def test_replay_meta_follows_the_run() -> None:
    short = run_scenario(enforce=False, max_turns=5)
    meta = replay_meta(short, GENERATED_BY_RECORDER)
    assert (meta["enforce"], meta["harness_cap"], meta["driver"]) == (False, 5, "scripted")
    assert meta["generated_by"] == GENERATED_BY_RECORDER
    llm_meta = replay_meta(run_scenario(enforce=True, driver=Finisher("llm")), "g")
    assert llm_meta["driver"] == "llm"
    assert llm_meta["id"] == "poisoned-briefing-enforced-llm"
