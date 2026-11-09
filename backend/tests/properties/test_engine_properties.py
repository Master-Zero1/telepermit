"""Property tests for the Engine (CONTRACTS section 5). Shared world and strategies live here."""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from telepermit.audit import BORDER_CHECK, RUN_ENDED, RUN_STARTED, STATUS_REFUSED
from telepermit.clock import TickClock
from telepermit.drivers.base import Proposal
from telepermit.engine import AgentNotAlive, Engine
from telepermit.identity import BAD_SIGNATURE, Authority, Identity
from telepermit.permit import Permit
from telepermit.place import REFUSE, Place
from telepermit.tools import VaultTools, library_tools, vault_tools

# DEMO ONLY seeded authority, fine for tests.
AUTHORITY = Authority.from_seed("home-authority", b"telepermit-demo-authority")
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
LIBRARY_CEILING = Permit(60.0, 30, 60, SIX_ACTIONS)
VAULT_CEILING = Permit(60.0, 30, 40, frozenset({"read_records", "go:library"}))


@dataclasses.dataclass
class World:
    engine: Engine
    clock: TickClock
    places: dict[str, Place]
    vault: VaultTools


def make_identity() -> Identity:
    return AUTHORITY.issue("briefing-bot-001", CLASS, 0.0)


def new_world(
    permit: Permit,
    *,
    enforce: bool = True,
    identity: Identity | None = None,
    start_place: str = "library",
) -> World:
    """A fresh world on every call: new places, new tool state, new clock."""
    trusted = {AUTHORITY.name: AUTHORITY.public_key}
    classes = frozenset({CLASS})
    vault = vault_tools()
    places = {
        "library": Place("library", library_tools(), LIBRARY_CEILING, trusted, classes),
        "vault": Place("vault", vault.tools, VAULT_CEILING, trusted, classes),
    }
    clock = TickClock(0.0)
    engine = Engine(places, identity or make_identity(), permit, start_place, clock, enforce)
    return World(engine, clock, places, vault)


POOL = [
    "read_document",
    "search_archive",
    "read_records",
    "export_records",
    "go:vault",
    "go:library",
    "finish",
    "bogus",
]
ADVERSARIAL = [
    "unknown",
    "",
    " read_records ",
    "read_rec\u043erds",
    "go:v\u00e4lts",
    "go:",
    "go:nowhere",
]
REQUIRED_KEY = {"read_document": "name", "search_archive": "query", "export_records": "destination"}
PERMIT_CANDIDATES = [action for action in POOL + ADVERSARIAL if action != "finish"]

texts = st.text(max_size=20)


@st.composite
def proposals(draw: st.DrawFn) -> Proposal:
    """A proposal from the action pool plus adversarial strings, with valid args (Group A)."""
    action = draw(st.sampled_from(POOL + ADVERSARIAL))
    key = REQUIRED_KEY.get(action)
    return Proposal(action, {key: draw(texts)} if key else {})


@st.composite
def permits(draw: st.DrawFn) -> Permit:
    """A valid permit that always allows go:vault."""
    lifetime_s = draw(
        st.one_of(
            st.sampled_from([0.0, 0.5, 1.0, 5.0, 60.0]),
            st.floats(min_value=0, max_value=120, allow_nan=False, allow_infinity=False),
        )
    )
    max_steps = draw(st.integers(min_value=0, max_value=40))
    allowance = draw(st.one_of(st.integers(min_value=0, max_value=8), st.integers(0, 80)))
    allowed = draw(st.frozensets(st.sampled_from(PERMIT_CANDIDATES))) | {"go:vault"}
    return Permit(lifetime_s, max_steps, allowance, allowed)


clock_advances = st.sampled_from([0.0, 0.0, 0.0, 0.5, 1.0, 30.0, 100.0])
step_sequences = st.lists(st.tuples(clock_advances, proposals()), max_size=40)

VALID_SIGNATURE = make_identity().signature


def flip_bit(signature: bytes, bit: int) -> bytes:
    flipped = bytearray(signature)
    flipped[bit // 8] ^= 1 << (bit % 8)
    return bytes(flipped)


forged_signatures = st.one_of(
    st.binary(max_size=128).filter(lambda signature: signature != VALID_SIGNATURE),
    st.integers(min_value=0, max_value=len(VALID_SIGNATURE) * 8 - 1).map(
        lambda bit: flip_bit(VALID_SIGNATURE, bit)
    ),
)


# Feature: engine-audit, Property 9
@given(permit=permits(), signature=forged_signatures)
def test_p3_9_forged_identity_three_event_refusal(permit: Permit, signature: bytes) -> None:
    """Property P3.9: a forged identity at spawn gives exactly RUN_STARTED, BORDER_CHECK(REFUSE,
    BAD_SIGNATURE), RUN_ENDED(REFUSED), and the agent can never act. Validates: Requirements 3.9"""
    forged = dataclasses.replace(make_identity(), signature=signature)
    world = new_world(permit, identity=forged)
    events = world.engine.events
    assert [event.type for event in events] == [RUN_STARTED, BORDER_CHECK, RUN_ENDED]
    started, border, ended = events
    assert border.data["decision"] == REFUSE
    assert border.data["reason"] == BAD_SIGNATURE
    assert border.data["permit_after"] == started.data["permit"]
    assert border.data["narrowed_fields"] == []
    assert border.data["cost"] == 0
    assert border.data["via_action"] is None
    assert ended.data["status"] == STATUS_REFUSED
    assert world.engine.state.status == STATUS_REFUSED
    with pytest.raises(AgentNotAlive):
        world.engine.step(Proposal("finish", {}))
