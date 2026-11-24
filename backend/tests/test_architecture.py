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
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

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


# Spec 6 additions (task 7.1). The checks above are unchanged. The urllib check below also scans
# tests/, and the llm.py checks pin its docstring and the origin of every import it makes.

TESTS_ROOT = Path(__file__).resolve().parent
LLM_MODULE = PACKAGE_ROOT / "drivers" / "llm.py"
URLLIB_FACTORY = "build_gemini_client"
ANTHROPIC_FACTORY = "build_client"


class UrllibImport(NamedTuple):
    """One static import of urllib or a urllib submodule, with its nearest enclosing function."""

    filename: str
    line: int
    module: str
    function: str | None


def _imports_with_function(
    node: ast.AST, function: str | None = None
) -> Iterator[tuple[ast.Import | ast.ImportFrom, str | None]]:
    """Every import node under node, in source order, with its nearest enclosing function name."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import | ast.ImportFrom):
            yield child, function
        is_function = isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        yield from _imports_with_function(child, child.name if is_function else function)


def _imported_modules(node: ast.Import | ast.ImportFrom) -> list[str]:
    """The module names an import node names; a from-import keeps its leading dots."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return ["." * node.level + (node.module or "")]


def check_urllib_imports(source: str, filename: str) -> list[UrllibImport]:
    """Every import of urllib or urllib.*, at any depth, with its enclosing function or None."""
    return [
        UrllibImport(filename, node.lineno, module, function)
        for node, function in _imports_with_function(ast.parse(source))
        for module in _imported_modules(node)
        if module.split(".")[0] == "urllib"
    ]


def _is_banned_module(module: str) -> bool:
    """True when a dotted module path (leading dots allowed) names a banned runtime module."""
    parts = module.lstrip(".").split(".")
    if parts[0] == "telepermit":
        return len(parts) > 1 and parts[1] in BANNED_IN_DRIVERS
    return parts[0] in BANNED_IN_DRIVERS


def _banned_targets(node: ast.AST) -> list[tuple[str, str]]:
    """(module, imported names) for each banned target an import node reaches."""
    if isinstance(node, ast.Import):
        return [
            (alias.name, alias.asname or alias.name)
            for alias in node.names
            if _is_banned_module(alias.name)
        ]
    if not isinstance(node, ast.ImportFrom):
        return []
    base = "." * node.level + (node.module or "")
    names = [alias.name for alias in node.names]
    if node.module and _is_banned_module(base):
        return [(base, ", ".join(names))]
    relative_package = node.level > 0 and not node.module
    absolute_package = node.level == 0 and node.module == "telepermit"
    if not (relative_package or absolute_package):
        return []
    separator = "." if node.module else ""
    return [(f"{base}{separator}{name}", name) for name in names if name in BANNED_IN_DRIVERS]


def describe_banned_imports(source: str, filename: str) -> list[str]:
    """Invariant 2 breaches as "<file>:<line>: imports <module> (<names>)", at any depth."""
    return [
        f"{filename}:{node.lineno}: imports {module} ({names})"
        for node in ast.walk(ast.parse(source))
        for module, names in _banned_targets(node)
    ]


def _allowed_in_llm(module: str, function: str | None) -> bool:
    """Stdlib, telepermit.drivers (absolute or one-dot relative), or anthropic in build_client."""
    if module.startswith("."):
        return not module.startswith("..")
    top = module.split(".")[0]
    if top in sys.stdlib_module_names:
        return True
    if module == "telepermit.drivers" or module.startswith("telepermit.drivers."):
        return True
    return top == "anthropic" and function == ANTHROPIC_FACTORY


def check_llm_imports(source: str, filename: str) -> list[str]:
    """Imports in drivers/llm.py from outside stdlib, telepermit.drivers and build_client's SDK."""
    return [
        f"{filename}:{node.lineno}: imports {module} (in {function or 'module level'})"
        for node, function in _imports_with_function(ast.parse(source))
        for module in _imported_modules(node)
        if not _allowed_in_llm(module, function)
    ]


def _relative_sources(root: Path) -> list[tuple[str, str]]:
    """(posix path relative to root, source text) for every Python file under root."""
    return [
        (path.relative_to(root).as_posix(), path.read_text(encoding="utf-8"))
        for path in collect_sources(root)
    ]


def test_urllib_checker_self_test() -> None:
    """The urllib checker reports bad snippets with their enclosing function.

    Validates: Requirements 6.6.1, 6.12.3
    """
    assert check_urllib_imports("import urllib.request", "bad.py") == [
        UrllibImport("bad.py", 1, "urllib.request", None)
    ]
    assert check_urllib_imports("from urllib.parse import quote", "bad.py") == [
        UrllibImport("bad.py", 1, "urllib.parse", None)
    ]
    assert check_urllib_imports("def helper():\n    import urllib.request\n", "bad.py") == [
        UrllibImport("bad.py", 2, "urllib.request", "helper")
    ]
    assert check_urllib_imports("import json, urllib", "bad.py") == [
        UrllibImport("bad.py", 1, "urllib", None)
    ]
    nested = f"def {URLLIB_FACTORY}():\n    from urllib import request\n"
    assert check_urllib_imports(nested, "ok.py") == [
        UrllibImport("ok.py", 2, "urllib", URLLIB_FACTORY)
    ]
    for snippet in ["import json", "import urllib3", "x = 'urllib.request.build_opener'"]:
        assert check_urllib_imports(snippet, "good.py") == [], snippet


def test_package_imports_urllib_only_in_gemini_factory() -> None:
    """No package module imports urllib except inside build_gemini_client in drivers/llm.py.

    Zero hits are allowed here; the at-least-one-hit check belongs to task 8.1.
    Validates: Requirements 6.6.1, 6.12.3
    """
    sources = _relative_sources(PACKAGE_ROOT)
    assert "drivers/llm.py" in {name for name, _ in sources}
    offenders = [
        hit
        for name, source in sources
        for hit in check_urllib_imports(source, name)
        if not (hit.filename == "drivers/llm.py" and hit.function == URLLIB_FACTORY)
    ]
    assert offenders == []


def test_tests_do_not_import_urllib() -> None:
    """No module under tests/ imports urllib; naming it in a string is not an import.

    Validates: Requirements 6.12.3
    """
    sources = _relative_sources(TESTS_ROOT)
    assert "test_architecture.py" in {name for name, _ in sources}
    hits = [hit for name, source in sources for hit in check_urllib_imports(source, name)]
    assert hits == []


def test_describe_banned_imports_self_test() -> None:
    """Every banned form (absolute, relative, package, in-function) is described; good ones pass.

    Validates: Requirements 6.11.1, 6.11.7
    """
    for snippet in BAD_IMPORTS:
        assert describe_banned_imports(snippet, "bad.py"), snippet
    for snippet in GOOD_SNIPPETS:
        assert describe_banned_imports(snippet, "good.py") == [], snippet


def test_describe_banned_imports_names_module_and_name() -> None:
    """A banned import is reported with the offending module and the imported name.

    Validates: Requirements 6.11.7
    """
    source = "from telepermit.engine import Engine"
    assert describe_banned_imports(source, "bad.py") == [
        "bad.py:1: imports telepermit.engine (Engine)"
    ]
    assert describe_banned_imports("from telepermit import engine, permit", "bad.py") == [
        "bad.py:1: imports telepermit.engine (engine)"
    ]
    assert describe_banned_imports("def f():\n    from ..place import Place\n", "bad.py") == [
        "bad.py:2: imports ..place (Place)"
    ]


def test_drivers_have_no_described_banned_imports() -> None:
    """No module in drivers/, including llm.py, imports engine, identity, place or tools.

    Validates: Requirements 6.11.1, 6.11.7
    """
    sources = [
        (name, source)
        for name, source in _relative_sources(PACKAGE_ROOT)
        if name.startswith("drivers/")
    ]
    assert "drivers/llm.py" in {name for name, _ in sources}
    violations = [
        line for name, source in sources for line in describe_banned_imports(source, name)
    ]
    assert violations == []


def test_llm_module_docstring_and_future_import() -> None:
    """drivers/llm.py opens with a docstring naming CONTRACTS section 7 and has future annotations.

    Validates: Requirements 6.11.6
    """
    tree = ast.parse(LLM_MODULE.read_text(encoding="utf-8"))
    first = tree.body[0]
    assert isinstance(first, ast.Expr)
    assert isinstance(first.value, ast.Constant)
    assert isinstance(first.value.value, str)
    assert "CONTRACTS section 7" in first.value.value
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    )


def test_llm_import_checker_self_test() -> None:
    """The llm.py import checker rejects non-stdlib imports and anthropic outside build_client.

    Validates: Requirements 6.13.4
    """
    bad = [
        "import requests",
        "import anthropic",
        "def other():\n    import anthropic\n",
        "from telepermit.engine import Engine",
        "from telepermit.permit import Permit",
        "from .. import permit",
    ]
    for snippet in bad:
        assert check_llm_imports(snippet, "bad.py"), snippet
    good = [
        "from __future__ import annotations",
        "import copy",
        "from collections.abc import Mapping",
        "from telepermit.drivers import FINISH_ACTION",
        "from telepermit.drivers.base import Proposal",
        "from .base import Observation",
        f"def {ANTHROPIC_FACTORY}():\n    import anthropic\n",
        f"def {URLLIB_FACTORY}():\n    import urllib.request\n",
    ]
    for snippet in good:
        assert check_llm_imports(snippet, "good.py") == [], snippet


def test_llm_imports_are_stdlib_drivers_or_anthropic() -> None:
    """Every import in drivers/llm.py is stdlib, telepermit.drivers, or anthropic in build_client.

    Validates: Requirements 6.13.4
    """
    assert check_llm_imports(LLM_MODULE.read_text(encoding="utf-8"), "drivers/llm.py") == []


# Spec 6 addition (task 8.1): the factory must hold the urllib import that the confinement test
# above allows, so the confinement test cannot pass vacuously.
def test_gemini_factory_holds_a_urllib_import() -> None:
    """build_gemini_client in drivers/llm.py holds at least one urllib import.

    Validates: Requirements 6.6.1, 6.12.3
    """
    hits = [
        hit
        for hit in check_urllib_imports(LLM_MODULE.read_text(encoding="utf-8"), "drivers/llm.py")
        if hit.function == URLLIB_FACTORY
    ]
    assert hits, "no urllib import inside build_gemini_client in drivers/llm.py"
