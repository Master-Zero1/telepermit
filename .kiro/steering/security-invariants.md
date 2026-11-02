# TelePermit: security invariants (never violate, never edit without the user's approval)

1. Only `engine.py` may call `Place.execute` (which runs a tool's `fn`). No other module executes tools.
2. Modules under `drivers/` never import `engine`, `identity` signing code (`Authority`), or tool executors. Drivers only see an `Observation` and return a `Proposal`.
3. Private keys never leave the `Authority` object and never appear in logs, observations, replays or error messages. (The scenario uses a deterministic DEMO-ONLY seed key; this is documented in code and the README.)
4. Every state transition emits exactly one audit event, in order, with contiguous `seq`.
5. Limit checks happen BEFORE an action runs. A breaching action never executes.
6. An imposed permit is never wider than the requested one, on any field.
7. A killed, finished or refused agent can never act again; `step()` on it raises `AgentNotAlive`.
8. Counters (`step`, `spent`, born time) never reset or decrease, including across border crossings.
9. The agent never sees its permit, its spend, or any key.

Enforcement: `tests/test_architecture.py` parses imports with `ast` and fails CI if invariants 1 and 2 are broken. Property tests cover 4 to 8.
When a change would touch an invariant, stop and ask the user first.
