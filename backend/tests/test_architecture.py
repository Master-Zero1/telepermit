"""Architecture tests for security invariants 1 and 2, checked statically with ast (task 8).

Invariant 1: only engine.py calls Place.execute. Invariant 2: nothing under drivers/ imports the
engine, identity, place or tools modules. The checkers are pure functions over a source string, so
the self-test can feed them deliberately bad snippets. Tests are not scanned.

Known limitation: this is a static check. It does not detect dynamic imports (importlib or
__import__), getattr(place, "execute"), aliasing such as run = place.execute, or attribute access
through a bare import telepermit. It reduces accidental breaches and is not a sandbox.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "telepermit"
BANNED_IN_DRIVERS = frozenset({"engine", "identity", "place", "tools"})


def _banned_import(node: ast.AST) -> str | None:
    """The banned module an import node reaches, or None. Covers every static import form."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            parts = alias.name.split(".")
            if parts[0] in BANNED_IN_DRIVERS:
                return alias.name
            if parts[0] == "telepermit" and len(parts) > 1 and parts[1] in BANNED_IN_DRIVERS:
                return alias.name
    elif isinstance(node, ast.ImportFrom):
        parts = node.module.split(".") if node.module else []
        dots = "." * node.level
        if node.level > 0 or (parts and parts[0] != "telepermit"):
            if parts and parts[0] in BANNED_IN_DRIVERS:
                return f"{dots}{node.module}"
            if not parts:
                for alias in node.names:
                    if alias.name in BANNED_IN_DRIVERS:
                        return f"{dots}{alias.name}"
        elif parts and parts[0] == "telepermit":
            if len(parts) > 1 and parts[1] in BANNED_IN_DRIVERS:
                return str(node.module)
            if len(parts) == 1:
                for alias in node.names:
                    if alias.name in BANNED_IN_DRIVERS:
                        return f"telepermit.{alias.name}"
    return None


def check_driver_imports(source: str, filename: str) -> list[str]:
    """Violations of invariant 2: any import of a banned module, at any depth in the file."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        banned = _banned_import(node)
        if banned is not None:
            violations.append(f"{filename}:{node.lineno}: imports {banned}")
    return violations


def check_no_execute_calls(source: str, filename: str) -> list[str]:
    """Violations of invariant 1: any call of an attribute named execute. Definitions pass."""
    return [
        f"{filename}:{node.lineno}: calls .execute()"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]


def is_engine_module(relative_path: Path) -> bool:
    """True only for engine.py at the package root, not for a same-named file in a sub-package."""
    return relative_path.parts == ("engine.py",)


def collect_sources(package_root: Path) -> list[Path]:
    """Every Python source file under the package root."""
    return sorted(package_root.rglob("*.py"))


BAD_IMPORTS = [
    "import telepermit.engine",
    "import telepermit.engine as e",
    "import telepermit.place.sub",
    "import telepermit.tools",
    "import engine",
    "import identity",
    "from telepermit.engine import X",
    "from telepermit.identity import Authority",
    "from telepermit import engine",
    "from .engine import X",
    "from ..tools import Y",
    "from . import engine",
    "from .. import place",
    "def f():\n    from telepermit import identity\n",
    "if True:\n    import telepermit.place\n",
]
BAD_EXECUTE_CALLS = [
    'place.execute("x", {})',
    'Place.execute(p, "x", {})',
    'self.places["vault"].execute("x", {})',
    "def f(p):\n    return p.execute('x', {})\n",
]
GOOD_SNIPPETS = [
    "import json",
    "import anthropic.lib.tools",
    "from telepermit.drivers.base import Proposal",
    "from telepermit.audit import Event",
    "from telepermit.permit import Permit",
    "from . import base",
    "from .base import Observation",
    "class P:\n    def execute(self): ...\n",
    "place.execute_plan()",
    "value = obj.execution",
    "obj.execute_later()",
]


def test_checker_self_test_catches_bad_snippets() -> None:
    for snippet in BAD_IMPORTS:
        assert check_driver_imports(snippet, "bad.py"), snippet
    for snippet in BAD_EXECUTE_CALLS:
        assert check_no_execute_calls(snippet, "bad.py"), snippet


def test_checker_self_test_passes_good_snippets() -> None:
    for snippet in GOOD_SNIPPETS:
        assert check_driver_imports(snippet, "good.py") == [], snippet
        assert check_no_execute_calls(snippet, "good.py") == [], snippet


def test_is_engine_module_cases() -> None:
    assert is_engine_module(Path("engine.py"))
    assert not is_engine_module(Path("drivers/engine.py"))
    assert not is_engine_module(Path("place.py"))
    assert not is_engine_module(Path("drivers/__init__.py"))


def test_drivers_do_not_import_runtime_modules() -> None:
    """Security invariant 2."""
    violations: list[str] = []
    for path in collect_sources(PACKAGE_ROOT):
        relative = path.relative_to(PACKAGE_ROOT)
        if relative.parts[0] == "drivers":
            source = path.read_text(encoding="utf-8")
            violations += check_driver_imports(source, relative.as_posix())
    assert violations == []


def test_only_engine_calls_execute() -> None:
    """Security invariant 1."""
    violations: list[str] = []
    for path in collect_sources(PACKAGE_ROOT):
        relative = path.relative_to(PACKAGE_ROOT)
        if not is_engine_module(relative):
            source = path.read_text(encoding="utf-8")
            violations += check_no_execute_calls(source, relative.as_posix())
    assert violations == []


def test_walker_is_not_vacuous() -> None:
    """A wrong path must not let the scans pass by finding nothing."""
    assert PACKAGE_ROOT.is_dir()
    found = {path.relative_to(PACKAGE_ROOT).as_posix() for path in collect_sources(PACKAGE_ROOT)}
    assert {"engine.py", "place.py", "drivers/base.py"} <= found
