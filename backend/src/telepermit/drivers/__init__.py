"""Agent drivers. A driver sees an Observation and returns a Proposal (CONTRACTS section 7).

FINISH_ACTION and GO_PREFIX are the two action literals that drivers share with the engine.
Drivers cannot import the engine (security invariant 2), so the literals are defined here, and a
test pins them equal to the ones in engine.py.
"""

from __future__ import annotations

from typing import Final

FINISH_ACTION: Final = "finish"
GO_PREFIX: Final = "go:"
