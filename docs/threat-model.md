# Threat model

Scope: an LLM agent that reads untrusted text (a document, a web page, a tool result) and can be talked into taking actions its operator did not intend. The question is what the runtime does about that.

Short answer: the engine enforces the permit. It does not judge intent. An action that is inside the permit runs, whoever suggested it.

Telescript facts are limited to the list in the README. The checks described here are TelePermit's own design.

## What permits stop

| Threat | Example from this repository | What happens |
|---|---|---|
| Spending past the allowance | The enforced replay: the agent loops on `read_records` (cost 3 each) until `spent + cost` would be 41 against the Vault's limit of 40. | `KILLED ALLOWANCE_EXCEEDED`. The breaching call never executes. |
| An action the permit does not list | The injected agent calls `export_records` in the Vault, whose imposed permit allows only `read_records` and `go:library`. | `DENIED NOT_IN_PERMIT`. Nothing is exported. The attempt uses a step and the agent stays alive. |
| A loop of denied actions | An agent that keeps calling a forbidden action. | Each attempt uses a step, so the run ends in `KILLED STEPS_EXCEEDED`. |
| Running past the lifetime | An agent that is still acting after `lifetime_s` of simulated time. | `KILLED LIFETIME_EXCEEDED`. Exactly equal to the limit is allowed. |
| A forged identity | The forged-identity replay: the signature is replaced with zero bytes. | `BORDER_CHECK REFUSE BAD_SIGNATURE`, then `RUN_ENDED REFUSED`. No tool ever runs. |
| An unknown authority or a disallowed agent class | An identity signed by a key the place does not trust, or of a class the place does not admit. | `REFUSE` with `UNTRUSTED_AUTHORITY` or `CLASS_NOT_ALLOWED`. |
| An agent that arrives with more than a place allows | An agent that has already spent more than the destination's ceiling allowance. | `REFUSE` with `EXCEEDS_CEILING`. |
| A permit that widens at a border | A place that would hand out more than the agent asked for. | The imposed permit is the minimum of the requested permit and the place's ceiling on every field, so it is never wider. |
| Counters reset by crossing a border | An agent that tries to start fresh in the next place. | `steps` and `spent` carry across borders and never decrease. |
| Acting after death | Anything that calls `step()` on a killed, finished or refused agent. | `AgentNotAlive` is raised. |

## What permits do not stop

| Threat | Example | Why |
|---|---|---|
| An injection that stays inside the permit | If the Vault's permit listed `export_records`, the agent arrives with 2 spent, the first export (cost 20) brings it to 22 and it runs. The second would bring it to 42 against a limit of 40, so that one is killed. | The engine checks limits, not purpose. In this demo the export is blocked because the Vault's ceiling does not list it, not because the engine recognises the injection. |
| Harmful arguments to an allowed action | An allowed `export_records` call with an attacker's address as the destination. | The engine does not inspect arguments for intent. |
| Slow abuse inside the limits | An agent that leaks a little data per step within the step limit and the allowance. | Limits bound the total, not the pattern. |
| Misleading output | An agent that writes a false summary using only allowed reads. | Nothing checks the content the agent produces. |
| A compromised engine or host | Someone who edits the engine, the permits or the audit log on the host. | The engine is the trust boundary. Nothing protects it from its own host. |
| Prompt injection itself | A document that tells the model to ignore its task. | The runtime does not read or filter what the model reads. It only limits what the model can do. |

## Out of scope

| Item | Note |
|---|---|
| Real tools and real side effects | Every tool is simulated. A permit would not sandbox a real process. |
| Real networking and payments | Cut from the project. |
| More than one agent, and the same-place interaction rule | Not implemented. The demo has one agent. |
| Authentication and key management | The demo authority key is derived from a public seed, so anyone can reproduce it. Do not reuse that pattern. |
| The "size" cap | Not implemented. |
| Wall-clock time | Lifetime is simulated: 1.0 second per driver turn. |
| Live LLM behaviour | One run only: the Gemini driver (`gemini-3.5-flash-lite`, enforcement on) ended `FINISHED` after 4 steps. Its `export_records` attempt was `DENIED` by the permit and nothing was exported. The model never read the poisoned document, so this run does not show how a live model responds to the injection. The Anthropic driver has not been run live. All recorded replays are scripted. |
| Vulnerabilities in dependencies | `npm audit` reports 3 findings, all in dev tooling (the vitest chain), none in production dependencies. The fix is a breaking vitest upgrade, not applied. |

## Invariants

These hold for every run. Invariants 1 and 2 are enforced by `backend/tests/test_architecture.py`. Property tests cover 4 to 8.

1. Only `engine.py` may call `Place.execute` (which runs a tool's `fn`). No other module executes tools.
2. Modules under `drivers/` never import `engine`, `identity` signing code (`Authority`), or tool executors. Drivers only see an `Observation` and return a `Proposal`.
3. Private keys never leave the `Authority` object and never appear in logs, observations, replays or error messages. The scenario uses a deterministic DEMO-ONLY seed key.
4. Every state transition emits exactly one audit event, in order, with contiguous `seq`.
5. Limit checks happen before an action runs. A breaching action never executes.
6. An imposed permit is never wider than the requested one, on any field.
7. A killed, finished or refused agent can never act again. `step()` on it raises `AgentNotAlive`.
8. Counters (`step`, `spent`, born time) never reset or decrease, including across border crossings.
9. The agent never sees its permit, its spend, or any key.
