from __future__ import annotations

from hypothesis import settings

settings.register_profile("default", deadline=None, max_examples=200)
settings.load_profile("default")
