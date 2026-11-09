"""Property tests for the Engine (CONTRACTS section 5). Shared world and strategies live here."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from telepermit.audit import (
    BORDER_CHECK,
    DENIED,
    FINISHED,
    KILLED,
    NOT_IN_PLACE,
    RUN_ENDED,
    RUN_STARTED,
    STATUS_ALIVE,
    STATUS_FINISHED,
    STATUS_KILLED,
    STATUS_REFUSED,
    STEPS_EXCEEDED,
    TOOL_CALL,
    UNENFORCED,
    permit_json,
    reduce_events,
)
from telepermit.clock import TickClock
from telepermit.drivers.base import Proposal
from telepermit.engine import AgentNotAlive, Engine
from telepermit.identity import BAD_SIGNATURE, Authority, Identity
from telepermit.permit import Permit
from telepermit.place import ADMIT, REFUSE, Place
from telepermit.tools import VaultTools, library_tools, vault_tools

# DEMO ONLY seeded authority, fine for tests.
AUTHORITY = Authority.from_seed("home-authority", b"telepermit-demo-authority")
CLASS = "briefing-bot"
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
# The library ceiling allows every candidate action, so even adversarial permit entries survive
# the spawn narrowing and reach the NOT_IN_PLACE branch of the step algorithm.
LIBRARY_CEILING = Permit(60.0, 30, 60, frozenset(PERMIT_CANDIDATES))

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


def alive(engine: Engine) -> bool:
    return engine.state.status == STATUS_ALIVE


def play(
    world: World,
    sequence: list[tuple[float, Proposal]],
    after_each: Callable[[Engine], None] | None = None,
) -> None:
    """Drive the Engine with the sequence while it is ALIVE, advancing the clock before each."""
    for advance, proposal in sequence:
        if not alive(world.engine):
            return
        world.clock.advance(advance)
        world.engine.step(proposal)
        if after_each is not None:
            after_each(world.engine)


crossing_proposals = st.sampled_from(["go:vault", "go:library"]).map(
    lambda action: Proposal(action, {})
)
crossing_sequences = st.lists(
    st.tuples(clock_advances, st.one_of(proposals(), crossing_proposals)), max_size=40
)


# Feature: engine-audit, Property 1
@given(permit=permits(), sequence=step_sequences)
def test_p3_1_counters_within_current_permit(
    permit: Permit, sequence: list[tuple[float, Proposal]]
) -> None:
    """Property P3.1: while ALIVE, spent <= allowance and steps <= max_steps of the current permit.
    Validates: Requirements 3.4, 3.5, 3.6, 3.7, 3.8"""

    def check(engine: Engine) -> None:
        state = engine.state
        if state.status == STATUS_ALIVE:
            assert state.spent <= state.permit.allowance
            assert state.steps <= state.permit.max_steps

    world = new_world(permit)
    check(world.engine)
    play(world, sequence, check)


# Feature: engine-audit, Property 2
@given(
    permit=permits(),
    sequence=step_sequences,
    after=st.lists(proposals(), min_size=1, max_size=5),
)
def test_p3_2_after_kill_only_run_ended(
    permit: Permit, sequence: list[tuple[float, Proposal]], after: list[Proposal]
) -> None:
    """Property P3.2: after KILLED the only further event is RUN_ENDED, and step raises
    AgentNotAlive. Validates: Requirements 3.1, 3.7"""
    world = new_world(permit)
    engine = world.engine
    for advance, proposal in sequence:
        world.clock.advance(advance)
        emitted = engine.step(proposal)
        status = engine.state.status
        if status in (STATUS_KILLED, STATUS_FINISHED):
            cause = KILLED if status == STATUS_KILLED else FINISHED
            assert [event.type for event in emitted] == [cause, RUN_ENDED]
            break
    if engine.state.status in (STATUS_KILLED, STATUS_FINISHED):
        before = engine.events
        assert before[-1].type == RUN_ENDED
        for proposal in after:
            with pytest.raises(AgentNotAlive):
                engine.step(proposal)
        assert engine.events == before


# Feature: engine-audit, Property 3
@given(
    permit=permits(),
    signature=st.one_of(st.none(), st.none(), st.none(), forged_signatures),
    sequence=step_sequences,
)
def test_p3_3_one_event_per_transition(
    permit: Permit, signature: bytes | None, sequence: list[tuple[float, Proposal]]
) -> None:
    """Property P3.3: seq is contiguous from 0 and every transition emits exactly one event.
    Validates: Requirements 3.11"""
    identity = None
    if signature is not None:
        identity = dataclasses.replace(make_identity(), signature=signature)
    world = new_world(permit, identity=identity)
    engine = world.engine
    assert len(engine.events) == (2 if signature is None else 3)
    for advance, proposal in sequence:
        before = engine.events
        if not alive(engine):
            with pytest.raises(AgentNotAlive):
                engine.step(proposal)
            assert engine.events == before
            continue
        world.clock.advance(advance)
        emitted = engine.step(proposal)
        assert engine.events[len(before) :] == emitted
        if alive(engine):
            assert len(emitted) == 1
        else:
            assert len(emitted) == 2
            assert emitted[0].type in (KILLED, FINISHED)
            assert emitted[1].type == RUN_ENDED
    events = engine.events
    assert [event.seq for event in events] == list(range(len(events)))


# Feature: engine-audit, Property 4
@given(permit=permits(), sequence=crossing_sequences)
def test_p3_4_counters_monotone_permits_shrink(
    permit: Permit, sequence: list[tuple[float, Proposal]]
) -> None:
    """Property P3.4: step, spent and t never decrease, and permit fields never grow across any
    event. Validates: Requirements 3.8"""
    world = new_world(permit)
    seen = [world.engine.state.permit]

    def record(engine: Engine) -> None:
        seen.append(engine.state.permit)

    play(world, sequence, record)
    events = world.engine.events
    for previous, current in pairwise(events):
        assert current.step >= previous.step
        assert current.spent >= previous.spent
        assert current.t >= previous.t
    carried = [
        event.data["permit"] if event.type == RUN_STARTED else event.data["permit_after"]
        for event in events
        if event.type in (RUN_STARTED, BORDER_CHECK)
    ]
    for previous_json, current_json in pairwise(carried):
        assert current_json["lifetime_s"] <= previous_json["lifetime_s"]
        assert current_json["max_steps"] <= previous_json["max_steps"]
        assert current_json["allowance"] <= previous_json["allowance"]
        assert set(current_json["allowed_actions"]) <= set(previous_json["allowed_actions"])
    for previous_permit, current_permit in pairwise(seen):
        assert current_permit.lifetime_s <= previous_permit.lifetime_s
        assert current_permit.max_steps <= previous_permit.max_steps
        assert current_permit.allowance <= previous_permit.allowance
        assert current_permit.allowed_actions <= previous_permit.allowed_actions


# Feature: engine-audit, Property 5
@given(permit=permits(), sequence=step_sequences)
def test_p3_5_reduce_events_equals_state(
    permit: Permit, sequence: list[tuple[float, Proposal]]
) -> None:
    """Property P3.5: reduce_events(events) equals the engine's final place, steps, spent, permit
    and status. Validates: Requirements 3.11, 3.14"""

    def check(engine: Engine) -> None:
        state = engine.state
        assert reduce_events(engine.events) == {
            "place": state.place,
            "step": state.steps,
            "spent": state.spent,
            "permit": permit_json(state.permit),
            "status": state.status,
        }

    world = new_world(permit)
    check(world.engine)
    play(world, sequence, check)


# Feature: engine-audit, Property 6
@given(permit=permits(), sequence=crossing_sequences)
def test_p3_6_tool_call_names_tool_of_recorded_place(
    permit: Permit, sequence: list[tuple[float, Proposal]]
) -> None:
    """Property P3.6: TOOL_CALL events only name tools that exist in the place recorded on that
    event. Validates: Requirements 3.6"""
    world = new_world(permit)
    play(world, sequence)
    for event in world.engine.events:
        if event.type == TOOL_CALL:
            assert world.places[event.place].has_tool(event.data["action"])


ALWAYS_DENIED = [
    "bogus",
    "",
    " read_records ",
    "read_rec\u043erds",
    "go:",
    "go:nowhere",
    "go:v\u00e4lts",
    "go:library",
    "read_records",
    "export_records",
]


# Feature: engine-audit, Property 7
@given(permit=permits(), actions=st.lists(st.sampled_from(ALWAYS_DENIED), min_size=1, max_size=60))
def test_p3_7_denied_loop_ends_in_steps_exceeded(permit: Permit, actions: list[str]) -> None:
    """Property P3.7: a loop of denied actions ends in KILLED(STEPS_EXCEEDED).
    Validates: Requirements 3.4, 3.5"""
    world = new_world(permit)
    engine = world.engine
    limit = engine.state.permit.max_steps
    index = 0
    while alive(engine):
        engine.step(Proposal(actions[index % len(actions)], {}))
        index += 1
    events = engine.events
    assert len([event for event in events if event.type == DENIED]) == limit
    assert not [event for event in events if event.type == TOOL_CALL]
    killed, ended = events[-2], events[-1]
    assert killed.type == KILLED
    assert killed.data["reason"] == STEPS_EXCEEDED
    assert killed.data["limit"] == limit
    assert killed.data["observed"] == limit + 1
    assert ended.type == RUN_ENDED
    state = engine.state
    assert (state.status, state.place, state.spent) == (STATUS_KILLED, "library", 0)


# Feature: engine-audit, Property 8
@given(
    permit=permits(),
    signature=st.one_of(st.none(), st.none(), forged_signatures),
    sequence=crossing_sequences,
)
def test_p3_8_unenforced_no_kill_no_permit_denial(
    permit: Permit, signature: bytes | None, sequence: list[tuple[float, Proposal]]
) -> None:
    """Property P3.8: with enforcement off there is never a KILLED event or a permit-reason DENIED.
    Validates: Requirements 3.10"""
    identity = None
    if signature is not None:
        identity = dataclasses.replace(make_identity(), signature=signature)
    world = new_world(permit, enforce=False, identity=identity)
    engine = world.engine
    assert [event.type for event in engine.events] == [RUN_STARTED]
    play(world, sequence)
    events = engine.events
    assert KILLED not in [event.type for event in events]
    assert engine.state.status in (STATUS_ALIVE, STATUS_FINISHED)
    for event in events:
        if event.type == DENIED:
            assert event.data["reason"] == NOT_IN_PLACE
        if event.type == BORDER_CHECK:
            assert event.data["via_action"] is not None
            assert event.data["decision"] == ADMIT
            assert event.data["reason"] == UNENFORCED
            assert event.data["narrowed_fields"] == []
            assert event.data["permit_after"] == permit_json(permit)
            assert event.data["cost"] == 1
    for previous, current in pairwise(events):
        assert current.step >= previous.step
        assert current.spent >= previous.spent
