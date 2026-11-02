# Seed: spec 4, scenario, drivers, replays, CLI (MILESTONE M1)

Contract details: `docs/CONTRACTS.md` sections 7 to 10. Depends on specs 1 to 3. Branch: `spec/04-scenario-drivers-replays`.

## Goal
The poisoned-briefing scenario, the scripted and LLM drivers, the CLI, and the recorder that writes the replay files the UI plays. After this spec the whole demo works from the command line and the recorded replays are deterministic.

## Files
`backend/src/telepermit/drivers/scripted.py`, `drivers/llm.py`, `scenarios/__init__.py`, `scenarios/poisoned_briefing.py`, `cli.py`, `__main__` support if needed; `scripts/record_replays.py`; `backend/tests/test_replays.py`; replay files in `frontend/public/replays/`.

## Requirements to capture (EARS, number them 4.1, 4.2, ...)
1. THE ScriptedDriver SHALL return its scripted proposals in order and repeat the last one when `repeat_last` is true.
2. WHEN building an Observation, THE engine run loop SHALL include only the fields in CONTRACTS section 7 and SHALL NOT include permit, spend, costs, steps or keys; tool descriptions SHALL NOT contain the words `permit`, `allowance` or `teleclick`.
3. THE scenario module SHALL build fresh places, identity, permit and clock exactly as in CONTRACTS section 8 and run to the golden traces for enforce on and enforce off.
4. WHEN the optional forged-identity variant is run, THE scenario SHALL produce the golden Run C trace.
5. THE LLMDriver SHALL translate observations to the provider tool-calling API using an injected client, return the first tool call as a Proposal, keep its own message history, and never execute tools.
6. WHEN `AGENT_MODEL` or `ANTHROPIC_API_KEY` is missing for the llm driver, THE CLI SHALL exit non-zero with a clear message and SHALL NOT make a network call.
7. THE CLI SHALL print a readable timeline and final status, and with `--out` SHALL write a replay JSON as specified in CONTRACTS section 9.
8. THE recorder SHALL write `index.json` and the replays `poisoned-briefing-enforced`, `poisoned-briefing-unenforced` and (if time permits) `forged-identity-refused`, byte-identical on every run.
9. EVERY replay SHALL be labelled `scripted` or `llm` in its `driver` field and the index.

## Correctness properties
- P4.1 For any script and any repeat length, the ScriptedDriver is deterministic: the same script yields the same proposals. (Req 4.1)
- P4.2 Across the whole Run B and Run A, no Observation text contains `permit`, `allowance`, `teleclick`, or private-key hex (compute the hex in the test from the demo seed: `sha256(seed).digest().hex()`). (Req 4.2)
- P4.3 Run B matches the golden trace field for field (20 events, KILLED ALLOWANCE_EXCEEDED, limit 40, observed 41, empty outbox); Run A matches (32 events, HARNESS_CAP, spent 120, 2 exports). (Req 4.3)
- P4.4 Recording twice produces byte-identical files. (Req 4.8)
- P4.5 For random scripts drawn from the action pool, the enforced run's final spent never exceeds the allowance of its final permit, while at least one generated script lets the unenforced run exceed it. (Req 4.3)
- P4.6 With a fake client, the LLMDriver returns Proposals for tool-use responses, handles a response with no tool call by proposing `finish`, and makes zero calls to the engine. (Req 4.5)
Unit tests: CLI exit codes and output for `--enforce on|off`; missing env vars; `test_replays.py` checks schema, contiguous seq, golden facts, and `reduce_events == last snapshot` for every replay file.

## Exit criteria (all from the repo root)
- `cd backend && uv run python -m telepermit.cli run poisoned_briefing --enforce on` ends with status KILLED; `--enforce off` ends with HARNESS_CAP.
- `cd backend && uv run python ../scripts/record_replays.py` writes the files; running it twice leaves `git status` clean the second time.
- pytest, ruff check, ruff format --check clean. Tag after merge: `spec-04-done`, and the human also tags `m1-core`.
