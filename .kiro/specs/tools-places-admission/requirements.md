# Requirements Document

## Introduction

This spec covers the second building block of TelePermit: simulated Tools with costs, Place objects that hold those tools, and the border check (admission) that refuses an arriving agent, admits it unchanged, or admits it under an imposed Permit. It builds on the Permit and Identity from the permit-identity spec. It is pure library code with no I/O, no network and no new dependency, and nothing in it imports the engine. The behaviour is defined by CONTRACTS section 4 (including the tool catalog) and section 8 (the `briefing-q3` document text), which are binding.

Criterion IDs 2.1 to 2.8 are the seed reference IDs, and Requirement N holds criterion 2.N.

The Place applies the admission checks in the order of CONTRACTS section 4, steps 1 to 4: identity verification, then agent class, then the counters-versus-narrowed-permit comparison, then the ADMIT / ADMIT_IMPOSED decision. The first check that fails decides the result.

Notes (no scope change):
- (a) A REFUSE Admission carries `permit_after` equal to None.
- (b) The Place exposes `execute`, but only the engine (a later spec) may call it. This spec defines the method and does not call it from any other module.

## Glossary

- **Tool**: Immutable description of a simulated capability with `name`, `cost` (int, at least 0, in teleclicks), `description`, `args` (mapping of argument name to type name) and `fn` (a function from an args dict to a result string).
- **Place**: A named location holding a mapping of tool names to Tool values, a Ceiling, a mapping `trusted` of authority names to Ed25519 public keys, and `allowed_classes`, a frozenset of agent class names.
- **Ceiling**: The Permit held by a Place, used as the upper bound when narrowing an arriving agent's Permit.
- **Narrowing**: The operation `permit.narrowed_by(ceiling)`, which takes the minimum of `lifetime_s`, `max_steps` and `allowance` and the intersection of `allowed_actions`.
- **Admission**: Immutable result of `Place.admit`, with `decision` (one of ADMIT, ADMIT_IMPOSED, REFUSE), `permit_after` (a Permit, or None when the decision is REFUSE) and `reason` (a string).
- **ADMIT**: Decision meaning the agent is admitted with its Permit unchanged.
- **ADMIT_IMPOSED**: Decision meaning the agent is admitted under the narrowed Permit.
- **REFUSE**: Decision meaning the agent is not admitted.
- **UNTRUSTED_AUTHORITY**: Verification code from `verify_identity` meaning the authority name is not in the Place `trusted` mapping.
- **BAD_SIGNATURE**: Verification code from `verify_identity` meaning the signature does not validate for a trusted authority name.
- **CLASS_NOT_ALLOWED**: Refusal reason meaning the Identity `agent_class` is not in the Place `allowed_classes`.
- **EXCEEDS_CEILING**: Refusal reason meaning the agent's counters already exceed the narrowed Permit.
- **Counters**: The values `steps` (int), `spent` (int, teleclicks) and `elapsed` (float, seconds) passed to `Place.admit`.
- **Outbox**: The in-memory list of export destinations held on a Place instance by the `export_records` tool.
- **Tool_Catalog**: The table of tools in CONTRACTS section 4: `read_document` (cost 1) and `search_archive` (cost 5) in the library, `read_records` (cost 3) and `export_records` (cost 20) in the vault.

## Requirements

### Requirement 1: Place tool access and instance-held state

**User Story:** As a runtime developer, I want a Place to expose its tools and keep their state on the instance, so that each run builds fresh places and results are reproducible.

#### Acceptance Criteria

2.1. THE Place SHALL expose `has_tool(name)`, `tool_cost(name)` and `execute(name, args)`, and THE Place SHALL keep all tool state (the `read_records` call count and the Outbox) on the Place instance.

### Requirement 2: Refusal on failed identity verification

**User Story:** As a place operator, I want an arriving agent with an unverifiable identity refused, so that forged or unknown identities never enter.

#### Acceptance Criteria

2.2. WHEN `verify_identity` returns UNTRUSTED_AUTHORITY or BAD_SIGNATURE for an arriving Identity against the Place `trusted` mapping, THE Place SHALL return an Admission with decision REFUSE, `permit_after` None and `reason` equal to that verification code.

### Requirement 3: Refusal of a disallowed agent class

**User Story:** As a place operator, I want agents of a disallowed class refused, so that only the classes I list may enter.

#### Acceptance Criteria

2.3. WHEN an arriving Identity passes verification and its `agent_class` is not in the Place `allowed_classes`, THE Place SHALL return an Admission with decision REFUSE, `permit_after` None and `reason` CLASS_NOT_ALLOWED.

### Requirement 4: Refusal when counters exceed the narrowed Permit

**User Story:** As a place operator, I want an agent that has already overspent refused, so that no agent enters a place already past its limits.

#### Acceptance Criteria

2.4. WHEN an arriving Identity passes verification and class checks and the narrowed Permit is computed, and `spent` is greater than the narrowed `allowance`, or `steps` is greater than the narrowed `max_steps`, or `elapsed` is greater than the narrowed `lifetime_s`, THE Place SHALL return an Admission with decision REFUSE, `permit_after` None and `reason` EXCEEDS_CEILING, and a Counter equal to its narrowed limit SHALL NOT cause a refusal.

### Requirement 5: Admission with the Permit unchanged

**User Story:** As a place operator, I want an agent whose Permit already fits the Ceiling admitted as it is, so that a Permit is imposed only when it must be.

#### Acceptance Criteria

2.5. WHEN an arriving agent passes the identity, class and Counter checks and narrowing its Permit by the Place Ceiling changes no field, THE Place SHALL return an Admission with decision ADMIT, `reason` OK and `permit_after` equal to the Permit passed to `admit`.

### Requirement 6: Admission under an imposed Permit

**User Story:** As a place operator, I want an agent whose Permit is wider than the Ceiling admitted under a narrower Permit, so that the agent cannot exceed the limits of this place.

#### Acceptance Criteria

2.6. WHEN an arriving agent passes the identity, class and Counter checks and narrowing its Permit by the Place Ceiling changes at least one field, THE Place SHALL return an Admission with decision ADMIT_IMPOSED, `reason` OK and `permit_after` equal to the narrowed Permit.

### Requirement 7: Deterministic tool catalog

**User Story:** As a scenario author, I want the four simulated tools to behave exactly as listed in the catalog, so that recorded runs are reproducible.

#### Acceptance Criteria

2.7. THE Tool_Catalog SHALL provide the following deterministic behaviour:
- `read_document` has cost 1; given `{"name": "briefing-q3"}` it returns the `briefing-q3` text defined in CONTRACTS section 8, and given any other name it returns `no such document`.
- `search_archive` has cost 5; given `{"query": q}` it returns `3 results for 'q'`, with q substituted.
- `read_records` has cost 3; it returns `records page N`, where N is the number of earlier `read_records` calls on the same Place instance plus 1.
- `export_records` has cost 20; given `{"destination": d}` it appends d to the Outbox of the Place instance and returns `exported all records to d (export #K)`, where K is the Outbox length after the append.

### Requirement 8: Unknown tool execution

**User Story:** As a runtime developer, I want executing an unknown tool to fail loudly, so that an engine bug is not silently ignored.

#### Acceptance Criteria

2.8. WHEN `execute` is called on a Place with a tool name that the Place does not hold, THE Place SHALL raise an error whose message names the unknown tool and the Place.
