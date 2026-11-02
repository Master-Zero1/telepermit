# TelePermit: product

## What it is
TelePermit resurrects Telescript's permit system (General Magic, 1994) as a runtime that bounds LLM agents. An engine owns every tool call, meters it, checks agents at place borders, and destroys them the moment they exceed a limit. Limits live in the runtime, not in a prompt.

## Why it matters
LLM agents now hold real credentials. A limit written in a prompt is not a control. A runtime that enforces limits is.

## Hackathon context
Kiroween 2026, Resurrection category. Deadline Dec 4 2026, 2:00 PM PT. Judges score Impact, Kiro usage, Design, Innovation and Presentation equally. The demo must run with zero API keys and zero backend.

## MVP (build exactly this)
- One agent, two simulated places (Library, Vault) with different tool sets, one border crossing.
- Permit = lifetime, step limit, allowance (teleclicks), allowed actions.
- Signed identity (Ed25519). A place refuses an agent, admits it, or admits it under an imposed permit.
- The engine meters every tool call and kills the agent on breach.
- Audit log and a timeline UI that replays recorded runs.
- Demo: a prompt-injected document pushes the agent past its permit; the runtime terminates it; the log shows why. Shown side by side with the same run unenforced.

## Cut list (never build unless the user explicitly approves)
Payments, real networking, multi-agent swarms, same-place interaction rule, MCP proxy, auth, databases, UI polish beyond the timeline, Tailwind or component libraries.

## Honesty rules
- State what permits do NOT stop: an injection that stays inside the permit.
- Label each replay "scripted" or "live LLM".
- Never claim "first" or "nobody has done this".
