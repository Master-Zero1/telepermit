"""Unit tests for Engine construction and the spawn border check (CONTRACTS section 5, task 4)."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from telepermit.audit import (
    BORDER_CHECK,
    RUN_ENDED,
    RUN_STARTED,
    STATUS_ALIVE,
    STATUS_REFUSED,
    permit_json,
)
from telepermit.clock import TickClock
from telepermit.drivers.base import Proposal
from telepermit.engine import AgentNotAlive, Engine
from telepermit.identity import BAD_SIGNATURE, Authority, Identity
from telepermit.permit import Permit
from telepermit.place import ADMIT, ADMIT_IMPOSED, OK, REFUSE, Place
from telepermit.tools import VaultTools, library_tools, vault_tools

SEED = b"telepermit-demo-authority"
# DEMO ONLY seeded authority, fine for tests.
AUTHORITY = Authority.from_seed("home-authority", SEED)
CLASS = "briefing-bot"
SIX_ACTIONS = frozenset(
    {
        "read_document",
        "search_archive",
        "read_records",
        "export_records",
        "go:vault",
        "go:library",
    }
)
HOME = Permit(60.0, 30, 60, SIX_ACTIONS)
LIBRARY_CEILING = Permit(60.0, 30, 60, SIX_ACTIONS)
VAULT_CEILING = Permit(60.0, 30, 40, frozenset({"read_records", "go:library"}))


class CountingClock(TickClock):
    """A TickClock that counts how often now() is read."""

    def __init__(self) -> None:
        super().__init__(0.0)
        self.reads = 0

    def now(self) -> float:
        self.reads += 1
        return super().now()


def build_places() -> tuple[dict[str, Place], VaultTools]:
    trusted = {AUTHORITY.name: AUTHORITY.public_key}
    classes = frozenset({CLASS})
    vault = vault_tools()
    places = {
        "library": Place("library", library_tools(), LIBRARY_CEILING, trusted, classes),
        "vault": Place("vault", vault.tools, VAULT_CEILING, trusted, classes),
    }
    return places, vault


def make_identity() -> Identity:
    return AUTHORITY.issue("briefing-bot-001", CLASS, 0.0)


def make_engine(
    *,
    permit: Permit = HOME,
    enforce: bool = True,
    start_place: str = "library",
    identity: Identity | None = None,
    **info: str,
) -> Engine:
    places, _vault = build_places()
    return Engine(
        places,
        identity or make_identity(),
        permit,
        start_place,
        TickClock(0.0),
        enforce,
        **info,
    )


def test_construct_enforced_admit_emits_two_events() -> None:
    """Requirement 3.9: RUN_STARTED, then the spawn BORDER_CHECK at the start place."""
    engine = make_engine()
    events = engine.events
    assert [event.type for event in events] == [RUN_STARTED, BORDER_CHECK]
    assert [event.seq for event in events] == [0, 1]
    border = events[1]
    assert (border.place, border.step, border.spent) == ("library", 0, 0)
    assert border.data["place"] == "library"
    assert border.data["via_action"] is None
    assert border.data["decision"] == ADMIT
    assert border.data["reason"] == OK
    assert border.data["cost"] == 0
    assert border.data["narrowed_fields"] == []
    assert border.data["permit_after"] == permit_json(HOME)
    state = engine.state
    assert state.status == STATUS_ALIVE
    assert (state.place, state.steps, state.spent) == ("library", 0, 0)
    assert state.permit == HOME


def test_construct_imposed_permit_at_spawn() -> None:
    """Requirement 3.9: an imposed permit at spawn replaces the current permit."""
    engine = make_engine(start_place="vault")
    border = engine.events[1]
    assert border.data["decision"] == ADMIT_IMPOSED
    assert border.data["narrowed_fields"] == ["allowance", "allowed_actions"]
    narrowed = HOME.narrowed_by(VAULT_CEILING)
    assert border.data["permit_after"] == permit_json(narrowed)
    assert engine.state.permit == narrowed
    assert engine.state.place == "vault"


def test_construct_enforce_off_emits_run_started_only() -> None:
    """Requirement 3.9, 3.10: no spawn border check when enforcement is off."""
    engine = make_engine(enforce=False)
    assert [event.type for event in engine.events] == [RUN_STARTED]
    assert engine.events[0].data["enforce"] is False
    assert engine.state.permit == HOME
    assert engine.state.status == STATUS_ALIVE


def test_construct_unknown_start_place_raises_before_any_event() -> None:
    """An unknown start place raises ValueError before the clock is read or any event exists."""
    clock = CountingClock()
    places, _vault = build_places()
    with pytest.raises(ValueError):
        Engine(places, make_identity(), HOME, "nowhere", clock)
    assert clock.reads == 0


def test_run_started_data_fields() -> None:
    engine = make_engine(scenario="poisoned_briefing", driver="llm", task="Summarise the briefing.")
    started = engine.events[0]
    assert (started.seq, started.place, started.step, started.spent) == (0, "library", 0, 0)
    assert started.t == 0.0
    data = started.data
    assert data["scenario"] == "poisoned_briefing"
    assert data["driver"] == "llm"
    assert data["task"] == "Summarise the briefing."
    assert data["enforce"] is True
    assert data["permit"] == permit_json(HOME)
    assert data["identity"] == {
        "agent_id": "briefing-bot-001",
        "agent_class": CLASS,
        "authority": "home-authority",
        "issued_at": 0.0,
        "signature_hex": make_identity().signature_hex,
    }


def test_run_started_defaults() -> None:
    data = make_engine().events[0].data
    assert (data["scenario"], data["driver"], data["task"]) == ("", "scripted", "")


def test_run_started_identity_has_only_public_fields() -> None:
    """Security invariant 3: the log holds the public signature and no key material."""
    engine = make_engine(task="x")
    identity = engine.events[0].data["identity"]
    assert set(identity) == {"agent_id", "agent_class", "authority", "issued_at", "signature_hex"}
    private_hex = hashlib.sha256(SEED).digest().hex()
    text = json.dumps([event.to_dict() for event in engine.events], sort_keys=True)
    assert private_hex not in text


def test_state_is_fresh_frozen_snapshot() -> None:
    engine = make_engine()
    first = engine.state
    second = engine.state
    assert first == second
    assert first is not second
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.steps = 5  # type: ignore[misc]


def test_events_returns_a_copy() -> None:
    engine = make_engine()
    returned = engine.events
    returned.clear()
    assert len(engine.events) == 2


def test_forged_identity_refused_run_c() -> None:
    """Golden Run C: a signature of 64 zero bytes gives exactly three events."""
    forged = dataclasses.replace(make_identity(), signature=bytes(64))
    engine = make_engine(identity=forged)
    started, border, ended = engine.events
    assert [event.type for event in engine.events] == [RUN_STARTED, BORDER_CHECK, RUN_ENDED]
    assert [event.seq for event in engine.events] == [0, 1, 2]
    assert all((e.place, e.step, e.spent) == ("library", 0, 0) for e in engine.events)
    assert border.data["decision"] == REFUSE
    assert border.data["reason"] == BAD_SIGNATURE
    assert border.data["permit_after"] == started.data["permit"]
    assert border.data["narrowed_fields"] == []
    assert border.data["cost"] == 0
    assert border.data["via_action"] is None
    assert ended.data["status"] == STATUS_REFUSED
    assert engine.state.status == STATUS_REFUSED


def test_step_after_refused_raises() -> None:
    """Security invariant 7: a refused agent can never act."""
    forged = dataclasses.replace(make_identity(), signature=bytes(64))
    engine = make_engine(identity=forged)
    before = engine.events
    with pytest.raises(AgentNotAlive):
        engine.step(Proposal("read_document", {"name": "briefing-q3"}))
    assert engine.events == before
    assert engine.state.status == STATUS_REFUSED
