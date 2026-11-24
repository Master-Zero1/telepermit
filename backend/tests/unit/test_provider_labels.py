"""Unit tests for provider labels on live replays (CONTRACTS section 9, pending amendment).

Spec 6 (gemini-driver), task 6.1. Requirements tested here: 6.9.6, 6.9.7, 6.9.8, 6.9.9,
6.9.10, 6.9.11, 6.9.12.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator

import pytest

from telepermit.audit import permit_json
from telepermit.drivers.base import Observation, Proposal
from telepermit.drivers.llm import LLMDriver
from telepermit.scenarios.poisoned_briefing import (
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
ENFORCED: dict[str, bool] = {"enforce": True}
UNENFORCED: dict[str, bool] = {"enforce": False}
FORGED: dict[str, bool] = {"enforce": True, "forged": True}
GENERATOR = "some-generator"


@pytest.fixture(autouse=True)
def network_attempts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Block the socket entry points and record every attempt. Teardown fails if any occurred."""
    attempts: list[str] = []

    def blocker(operation: str) -> Callable[..., None]:
        def blocked(*args: object, **kwargs: object) -> None:
            attempts.append(operation)
            raise RuntimeError(f"network access blocked: {operation}")

        return blocked

    monkeypatch.setattr(socket.socket, "connect", blocker("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocker("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", blocker("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocker("getaddrinfo"))
    yield attempts
    if attempts:
        pytest.fail(f"network access attempted: {attempts}")


class ScriptedFinisher:
    """A scripted-labelled stand-in that finishes at once."""

    label = "scripted"

    def propose(self, observation: Observation) -> Proposal:
        return Proposal("finish", {})


class LlmFinisher:
    """An llm-labelled stand-in with no provider that finishes at once."""

    label = "llm"

    def propose(self, observation: Observation) -> Proposal:
        return Proposal("finish", {})


class GeminiFinisher(LlmFinisher):
    """An llm-labelled stand-in with provider gemini."""

    provider = "gemini"


class AnthropicFinisher(LlmFinisher):
    """An llm-labelled stand-in with provider anthropic."""

    provider = "anthropic"


class UnknownProviderFinisher(LlmFinisher):
    """An llm-labelled stand-in with a provider the scenario does not know."""

    provider = "openai"


IDENTITY_CASES = [
    (
        ENFORCED,
        ScriptedFinisher,
        "poisoned-briefing-enforced",
        "Poisoned briefing: limits enforced (scripted)",
    ),
    (
        ENFORCED,
        LlmFinisher,
        "poisoned-briefing-enforced-llm",
        "Poisoned briefing: limits enforced (live LLM)",
    ),
    (
        ENFORCED,
        GeminiFinisher,
        "poisoned-briefing-enforced-gemini",
        "Poisoned briefing: limits enforced (Gemini live LLM)",
    ),
    (
        ENFORCED,
        AnthropicFinisher,
        "poisoned-briefing-enforced-anthropic",
        "Poisoned briefing: limits enforced (Anthropic live LLM)",
    ),
    (
        UNENFORCED,
        ScriptedFinisher,
        "poisoned-briefing-unenforced",
        "Poisoned briefing: no enforcement (scripted)",
    ),
    (
        UNENFORCED,
        LlmFinisher,
        "poisoned-briefing-unenforced-llm",
        "Poisoned briefing: no enforcement (live LLM)",
    ),
    (
        UNENFORCED,
        GeminiFinisher,
        "poisoned-briefing-unenforced-gemini",
        "Poisoned briefing: no enforcement (Gemini live LLM)",
    ),
    (
        UNENFORCED,
        AnthropicFinisher,
        "poisoned-briefing-unenforced-anthropic",
        "Poisoned briefing: no enforcement (Anthropic live LLM)",
    ),
    (
        FORGED,
        ScriptedFinisher,
        "forged-identity-refused",
        "Forged identity refused at the border (scripted)",
    ),
    (
        FORGED,
        LlmFinisher,
        "forged-identity-refused-llm",
        "Forged identity refused at the border (live LLM)",
    ),
    (
        FORGED,
        GeminiFinisher,
        "forged-identity-refused-gemini",
        "Forged identity refused at the border (Gemini live LLM)",
    ),
    (
        FORGED,
        AnthropicFinisher,
        "forged-identity-refused-anthropic",
        "Forged identity refused at the border (Anthropic live LLM)",
    ),
]
VARIANTS = [ENFORCED, UNENFORCED, FORGED]
VARIANT_IDS = ["enforced", "unenforced", "forged"]


def baseline_meta(replay_id: str, title: str, enforce: bool) -> dict[str, object]:
    """The meta exactly as the Baseline_Commit builds it for a scripted run."""
    return {
        "id": replay_id,
        "title": title,
        "scenario": SCENARIO_NAME,
        "driver": "scripted",
        "enforce": enforce,
        "harness_cap": 30,
        "task": TASK,
        "home_permit": permit_json(HOME_PERMIT),
        "ceilings": {
            "library": permit_json(LIBRARY_CEILING),
            "vault": permit_json(VAULT_CEILING),
        },
        "tool_costs": {
            "read_document": 1,
            "search_archive": 5,
            "read_records": 3,
            "export_records": 20,
        },
        "document_text": BRIEFING_Q3_TEXT,
        "generated_by": GENERATOR,
    }


def test_llm_driver_provider_is_anthropic() -> None:
    """Requirement 6.9.6 (Anthropic half): LLMDriver exposes the provider anthropic."""
    assert LLMDriver.provider == "anthropic"


@pytest.mark.parametrize(
    ("kwargs", "driver_cls", "expected_id", "expected_title"),
    IDENTITY_CASES,
    ids=[case[2] for case in IDENTITY_CASES],
)
def test_replay_identity_follows_label_and_provider(
    kwargs: dict[str, bool],
    driver_cls: type[LlmFinisher] | type[ScriptedFinisher],
    expected_id: str,
    expected_title: str,
) -> None:
    """Requirements 6.9.7, 6.9.8, 6.9.10, 6.9.11: the twelve ids and titles, written out."""
    run = run_scenario(driver=driver_cls(), **kwargs)  # type: ignore[arg-type]
    replay_id, title = replay_identity(run)
    assert replay_id == expected_id, f"id is {replay_id}"
    assert title == expected_title, f"title is {title}"


@pytest.mark.parametrize("kwargs", VARIANTS, ids=VARIANT_IDS)
def test_gemini_and_anthropic_replays_differ(kwargs: dict[str, bool]) -> None:
    """Requirement 6.9.12: a Gemini run and an Anthropic run get different ids and titles."""
    gemini_run = run_scenario(driver=GeminiFinisher(), **kwargs)  # type: ignore[arg-type]
    anthropic_run = run_scenario(driver=AnthropicFinisher(), **kwargs)  # type: ignore[arg-type]
    gemini = replay_identity(gemini_run)
    anthropic = replay_identity(anthropic_run)
    assert gemini[0] != anthropic[0]
    assert gemini[1] != anthropic[1]


@pytest.mark.parametrize("kwargs", VARIANTS, ids=VARIANT_IDS)
def test_scripted_meta_equals_baseline(kwargs: dict[str, bool]) -> None:
    """Requirement 6.9.10: a scripted meta has no provider key and equals the baseline meta."""
    run = run_scenario(**kwargs)  # type: ignore[arg-type]
    meta = replay_meta(run, GENERATOR)
    assert "provider" not in meta
    assert set(meta) == META_KEYS
    replay_id, title = replay_identity(run)
    assert dict(meta) == baseline_meta(replay_id, title, kwargs["enforce"])


@pytest.mark.parametrize("kwargs", VARIANTS, ids=VARIANT_IDS)
def test_llm_without_provider_meta_has_no_provider(kwargs: dict[str, bool]) -> None:
    """Requirement 6.9.11: an llm driver without a provider writes no provider key."""
    run = run_scenario(driver=LlmFinisher(), **kwargs)  # type: ignore[arg-type]
    meta = replay_meta(run, GENERATOR)
    assert "provider" not in meta
    assert set(meta) == META_KEYS
    assert meta["driver"] == "llm"
    assert meta["id"].endswith("-llm")
    assert meta["title"].endswith("(live LLM)")


def test_gemini_meta_has_llm_driver_and_gemini_provider() -> None:
    """Requirement 6.9.9: the Gemini meta keeps driver llm and adds provider gemini."""
    meta = replay_meta(run_scenario(enforce=True, driver=GeminiFinisher()), GENERATOR)
    assert meta["id"] == "poisoned-briefing-enforced-gemini", f"id is {meta['id']}"
    assert meta["driver"] == "llm"
    assert meta.get("provider") == "gemini"
    assert set(meta) == META_KEYS | {"provider"}


def test_anthropic_meta_has_anthropic_provider() -> None:
    """Requirement 6.9.9: the Anthropic meta keeps driver llm and adds provider anthropic."""
    meta = replay_meta(run_scenario(enforce=True, driver=AnthropicFinisher()), GENERATOR)
    assert meta["id"] == "poisoned-briefing-enforced-anthropic", f"id is {meta['id']}"
    assert meta["driver"] == "llm"
    assert meta.get("provider") == "anthropic"


def test_unknown_provider_is_rejected() -> None:
    """Design `_provider_of`: an llm driver with a provider not in PROVIDER_NAMES is rejected."""
    with pytest.raises(ValueError):
        run_scenario(enforce=True, driver=UnknownProviderFinisher())
