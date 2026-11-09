"""The command line interface (CONTRACTS section 10).

Usage: python -m telepermit.cli run poisoned_briefing --enforce on|off [--driver scripted|llm]

The timeline is the operator's view of the audit log. It may show permits and limits, never keys.
The --out option is not implemented yet.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Final, TextIO

from telepermit.audit import (
    BORDER_CHECK,
    DENIED,
    FINISHED,
    KILLED,
    RUN_ENDED,
    RUN_STARTED,
    TOOL_CALL,
    Event,
)
from telepermit.drivers.llm import (
    ENV_API_KEY,
    ENV_MODEL,
    LLMDriver,
    LLMUnavailableError,
    build_client,
)
from telepermit.scenarios.poisoned_briefing import SCENARIO_NAME, ScenarioRun, run_scenario

SUMMARY_WIDTH: Final = 72
ELLIPSIS: Final = "..."
EXIT_OK: Final = 0
EXIT_PROBLEM: Final = 1
EXIT_USAGE: Final = 2
HEADER: Final = f"{'seq':>3}  {'type':<12}  {'place':<8}  {'step':>4}  {'spent':>5}  summary"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telepermit")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run a scenario and print its timeline")
    run.add_argument("scenario", choices=[SCENARIO_NAME])
    run.add_argument("--enforce", required=True, choices=["on", "off"])
    run.add_argument("--driver", choices=["scripted", "llm"], default="scripted")
    return parser


def _sanitise(text: str) -> str:
    """One printable ASCII line of at most SUMMARY_WIDTH characters."""
    spaced = "".join(char if char.isprintable() else " " for char in text)
    plain = " ".join(spaced.split()).encode("ascii", "backslashreplace").decode("ascii")
    if len(plain) > SUMMARY_WIDTH:
        return plain[: SUMMARY_WIDTH - len(ELLIPSIS)] + ELLIPSIS
    return plain


def _border_summary(data: Mapping[str, object]) -> str:
    text = f"{data['decision']} {data['reason']} -> {data['place']}"
    if data.get("via_action"):
        text += f" via {data['via_action']}"
    narrowed = data.get("narrowed_fields")
    if isinstance(narrowed, list) and narrowed:
        text += " narrowed: " + ", ".join(str(name) for name in narrowed)
    return text


def _summary(event: Event) -> str:
    data: Mapping[str, object] = event.data
    if event.type == RUN_STARTED:
        return f"enforce {'on' if data['enforce'] else 'off'}, driver {data['driver']}"
    if event.type == BORDER_CHECK:
        return _border_summary(data)
    if event.type == TOOL_CALL:
        return f"{data['action']} cost {data['cost']}: {data['result']}"
    if event.type == DENIED:
        return f"{data['action']} {data['reason']}"
    if event.type == KILLED:
        return f"{data['reason']} limit {data['limit']} observed {data['observed']}"
    if event.type == RUN_ENDED:
        return str(data["status"])
    return "" if event.type == FINISHED else event.type


def format_timeline(events: Sequence[Event]) -> list[str]:
    """The header line, then one ASCII line per event."""
    lines = [HEADER]
    for event in events:
        columns = (
            f"{event.seq:>3}  {event.type:<12}  {event.place:<8}  "
            f"{event.step:>4}  {event.spent:>5}  "
        )
        lines.append((columns + _sanitise(_summary(event))).rstrip())
    return lines


def _report(run: ScenarioRun, stdout: TextIO) -> int:
    for line in format_timeline(run.result.events):
        print(line, file=stdout)
    print(f"status: {run.result.status}", file=stdout)
    print(f"outbox: {len(run.outbox)}", file=stdout)
    return EXIT_OK


def _run_llm(enforce: bool, env: Mapping[str, str], stdout: TextIO, stderr: TextIO) -> int:
    missing = [name for name in (ENV_MODEL, ENV_API_KEY) if not env.get(name, "").strip()]
    if missing:
        names = ", ".join(missing)
        print(f"error: missing environment variable(s) for --driver llm: {names}", file=stderr)
        return EXIT_PROBLEM
    try:
        client = build_client(env[ENV_API_KEY].strip())
    except LLMUnavailableError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_PROBLEM
    driver = LLMDriver(client, env[ENV_MODEL].strip())
    try:
        run = run_scenario(enforce=enforce, driver=driver)
    except Exception as exc:
        # Only the type name is printed: SDK messages may contain the API key.
        print(f"error: run aborted: {type(exc).__name__} (details withheld; see docs)", file=stderr)
        return EXIT_PROBLEM
    return _report(run, stdout)


def _exit_code(code: object) -> int:
    if code is None:
        return EXIT_OK
    return code if isinstance(code, int) else EXIT_PROBLEM


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run the command line. Returns 0 for a final status, 1 for a problem, 2 for a usage error."""
    stdout = sys.stdout if out is None else out
    stderr = sys.stderr if err is None else err
    environment = os.environ if env is None else env
    try:
        with contextlib.redirect_stderr(stderr):
            args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc.code)
    enforce = args.enforce == "on"
    if args.driver == "llm":
        return _run_llm(enforce, environment, stdout, stderr)
    return _report(run_scenario(enforce=enforce), stdout)


if __name__ == "__main__":
    raise SystemExit(main())
