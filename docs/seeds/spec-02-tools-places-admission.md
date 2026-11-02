# Seed: spec 2, tools, places and admission

Contract details: `docs/CONTRACTS.md` section 4 (including the tool catalog). Depends on spec 1. Branch: `spec/02-tools-places-admission`.

## Goal
Simulated tools with costs, `Place` objects, and the border check that refuses, admits, or admits under an imposed permit.

## Files
`backend/src/telepermit/tools.py`, `place.py`; tests in `backend/tests/unit/` and `backend/tests/properties/`.

## Requirements to capture (EARS, number them 2.1, 2.2, ...)
1. THE Place SHALL expose `has_tool`, `tool_cost` and `execute`, and tool state SHALL live on the Place instance.
2. WHEN an arriving agent's identity fails verification, THE Place SHALL refuse it with the verification code.
3. WHEN an arriving agent's class is not allowed, THE Place SHALL refuse it with CLASS_NOT_ALLOWED.
4. WHEN the agent's counters (spent, steps, elapsed) already exceed the narrowed permit, THE Place SHALL refuse it with EXCEEDS_CEILING.
5. WHEN narrowing the permit by the place ceiling changes nothing, THE Place SHALL admit the agent with its permit unchanged (ADMIT).
6. WHEN narrowing changes any field, THE Place SHALL admit the agent under the narrowed permit (ADMIT_IMPOSED).
7. THE library tools `read_document` (cost 1) and `search_archive` (cost 5) and the vault tools `read_records` (cost 3) and `export_records` (cost 20) SHALL behave exactly as in the CONTRACTS catalog, deterministically.
8. WHEN an unknown tool name is executed, THE Place SHALL raise a clear error (the engine prevents this in normal use).

## Correctness properties
- P2.1 `permit_after` is never wider than the requested permit or the ceiling, on any field. (Req 2.5, 2.6)
- P2.2 An identity with an unknown authority, a corrupted signature, or a disallowed class is always refused. (Req 2.2, 2.3)
- P2.3 ADMIT happens if and only if narrowing changes nothing; otherwise ADMIT_IMPOSED. (Req 2.5, 2.6)
- P2.4 If counters exceed the narrowed limits the decision is REFUSE with EXCEEDS_CEILING, never an admission. (Req 2.4)
- P2.5 Two fresh places given the same call sequence return identical results; `export_records` outbox length equals the number of successful exports. (Req 2.1, 2.7)
Also unit tests for the exact catalog numbers and the `briefing-q3` document text (CONTRACTS section 8).

## Exit criteria
In `backend/`: pytest, ruff check and ruff format --check all clean; the five properties exist and pass. Branch ready for `MERGE`.
