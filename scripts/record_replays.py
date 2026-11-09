"""Record the replay files that the timeline UI plays (CONTRACTS section 10).

Run it with: uv --directory backend run python ../scripts/record_replays.py

It runs the scripted scenario with enforcement on (Run B) and off (Run A), writes one replay file
per run, and writes index.json last. There is no network, clock or randomness, so recording twice
gives byte-identical files. DEMO ONLY: the scenario key is derived from a public seed.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from telepermit.audit import IndexEntry, index_document, replay_document, write_json
from telepermit.scenarios.poisoned_briefing import (
    GENERATED_BY_RECORDER,
    replay_meta,
    run_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPLAY_DIR = REPO_ROOT / "frontend" / "public" / "replays"
INDEX_NAME = "index.json"


def record_all(output_dir: Path) -> list[Path]:
    """Write the replays and then the index into output_dir. Returns the paths in write order."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    entries: list[IndexEntry] = []
    for enforce in (True, False):
        run = run_scenario(enforce=enforce)
        meta = replay_meta(run, GENERATED_BY_RECORDER)
        file_name = f"{meta['id']}.json"
        path = output_dir / file_name
        write_json(path, replay_document(meta, run.result.events))
        written.append(path)
        entries.append(
            {
                "id": meta["id"],
                "title": meta["title"],
                "file": file_name,
                "driver": meta["driver"],
                "enforce": meta["enforce"],
            }
        )
    index_path = output_dir / INDEX_NAME
    write_json(index_path, index_document(entries))
    written.append(index_path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """Record all replays and print one line per file."""
    parser = argparse.ArgumentParser(description="Record the TelePermit replay files.")
    parser.add_argument("--output-dir", type=Path, default=REPLAY_DIR)
    args = parser.parse_args(argv)
    for path in record_all(args.output_dir):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
