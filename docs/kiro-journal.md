# Kiro journal

Dated, factual log of how Kiro was used on this project. It feeds the Devpost write-up. Never invent entries.

| Date | Kiro surface (IDE/CLI) | What I asked | What Kiro did well | What went wrong or surprised me | Feature used (spec / steering / hook / PBT / MCP / power / agent) |
|---|---|---|---|---|---|
| 2026-11-07 | Kiro IDE, Vibe session, model Claude Haiku 5.5 | PHASE 0 (hardened): scaffold backend, frontend, CI and README stub | Read the steering files and BUILD_PLAN first, checked preconditions, pinned Python 3.12 via uv, and ran backend pytest and ruff plus frontend build and vitest. Ruff's import check flagged my smoke test; I fixed it by hand. | I ran the three backend ruff and pytest commands in one batch, not one per call as quality.md requires. npm audit reports 3 dev-only vulnerabilities in vitest 3.2.7 and tinypool. The fix is a breaking vitest 5 upgrade, so I did not apply it. | Steering (workflow, quality, tech, structure, BUILD_PLAN read as context). No spec, hook or property test used yet. |
