"""A deterministic scripted driver (CONTRACTS section 7)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from telepermit.drivers import FINISH_ACTION
from telepermit.drivers.base import Observation, Proposal


def _copy(proposal: Proposal) -> Proposal:
    return Proposal(proposal.action, dict(proposal.args))


class ScriptedDriver:
    """Returns a fixed list of proposals in order. The same script always gives the same proposals.

    After the script ends it repeats the last proposal when repeat_last is true. With repeat_last
    false, or for an empty script, it proposes finish so that a run ends cleanly.
    """

    label: Final = "scripted"

    def __init__(self, script: Sequence[Proposal], repeat_last: bool = True) -> None:
        self._script = tuple(_copy(item) for item in script)
        self._repeat_last = repeat_last
        self._calls = 0

    def propose(self, observation: Observation) -> Proposal:
        """Return the next scripted proposal. The observation is ignored."""
        index = self._calls
        self._calls += 1
        if index < len(self._script):
            return _copy(self._script[index])
        if self._repeat_last and self._script:
            return _copy(self._script[-1])
        return Proposal(FINISH_ACTION, {})
