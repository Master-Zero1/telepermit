# TelePermit: repository structure

```
.
├── .kiro/steering/        always-on rules (this folder)
├── .kiro/specs/           created by Kiro's spec workflow
├── .kiro/hooks/           created through the Kiro hooks UI
├── backend/
│   ├── pyproject.toml
│   ├── src/telepermit/
│   │   ├── permit.py      Permit, narrowed_by
│   │   ├── identity.py    Identity, Authority, verify_identity
│   │   ├── tools.py       Tool, simulated tool factories, costs
│   │   ├── place.py       Place, Admission, admit()
│   │   ├── audit.py       Event models, PermitJSON, reduce_events, JSONL writer
│   │   ├── engine.py      Engine: ONLY module that executes tools
│   │   ├── clock.py       Clock protocol, TickClock
│   │   ├── drivers/       base.py, scripted.py, llm.py
│   │   ├── scenarios/     poisoned_briefing.py
│   │   └── cli.py
│   └── tests/             unit/, properties/, test_architecture.py, test_replays.py
├── frontend/              Vite + React + TS
│   └── public/replays/    index.json + recorded runs
├── scripts/record_replays.py
├── docs/                  BUILD_PLAN, CONTRACTS, PROGRESS, HOOKS, SUBMISSION, seeds/, kiro-journal.md
├── .github/workflows/     ci.yml, pages.yml
├── LICENSE, README.md, .gitignore, .env.example
```

Naming: snake_case Python, PascalCase React components, kebab-case file names for docs. One module per concept. Tests mirror source names.
Never move or rename these paths without updating this file and docs/CONTRACTS.md.
