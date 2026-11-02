# TelePermit: tech stack and commands

## Backend (folder: backend/)
- Python >=3.11 (developed on 3.12). src layout, package `telepermit`.
- Core deps: pydantic>=2.6, cryptography>=42. No web framework in core.
- Extras in pyproject `[project.optional-dependencies]`: `dev` = pytest, hypothesis, ruff; `llm` = anthropic; `api` = fastapi, uvicorn, httpx (optional, built only if the user asks).
- Build backend: hatchling, with `[tool.hatch.build.targets.wheel] packages = ["src/telepermit"]`.
- Pytest config: `testpaths = ["tests"]`. Ruff: line-length 100, select E,F,I,B,UP.
- Data models: pydantic v2 or frozen dataclasses. Inject the clock. No global mutable state. Add `from __future__ import annotations` to every module.
- Install: `cd backend && uv sync --extra dev`. Fallback: `python -m venv .venv && pip install -e ".[dev]"`.
- Test: `uv run pytest -q`. Lint: `uv run ruff check . && uv run ruff format --check .`.

## Frontend (folder: frontend/)
- Vite + React + TypeScript. Plain CSS only (one stylesheet, CSS variables). No Tailwind, no UI kit.
- Tests: vitest (node environment) for pure logic. Scripts: `dev`, `build` (`tsc -b && vite build`), `test` (`vitest run`).
- `vite.config.ts` must set `base: './'` so the build works on any GitHub Pages path.
- Fetch replays from `./replays/index.json` (relative URL). No external network requests, no CDN fonts, no analytics.
- Style: retro terminal (amber on dark, monospace system font stack). No third-party logos or trademarks.

## LLM (optional driver)
- Anthropic SDK behind the `AgentDriver` interface. Model name comes only from env `AGENT_MODEL`; never hard-code a model name. Key from `ANTHROPIC_API_KEY`. Tests use a fake client and never hit the network.

## Process rules
- Never start a long-running process (dev servers, watchers). Verify with one-shot commands: pytest, ruff, `npm run build`, `npm test`.
- Never install global packages. Never run `sudo`.
- Never commit `.env`, keys, `node_modules`, `.venv`, `frontend/dist`.
