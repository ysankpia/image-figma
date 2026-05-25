from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
IMAGE_MATH_ROOT = APP_ROOT / "image_math"
JSON_TOOLS = APP_ROOT / "json_tools.py"

IMAGE_MATH_DEPS = ("numpy", "PIL", "skimage")
DOMAIN_IMPORT_PREFIXES = (
    "app.source_ui_physical_graph",
    "app.m29_replay_plan",
    "app.plan_materializer",
    "app.upload_preview",
    "source_ui_physical_graph",
    "m29_replay_plan",
    "plan_materializer",
    "upload_preview",
)
DOMAIN_DECISION_STRINGS = (
    "pixelOwner",
    "replayDecision",
    "cleanupAuthorization",
    "materialize",
    "autoLayout",
    "componentIdentity",
)


def test_image_math_dependencies_are_imported_only_inside_image_math() -> None:
    violations: list[str] = []
    for path in app_python_files():
        if path.is_relative_to(IMAGE_MATH_ROOT):
            continue
        for imported in imported_modules(path):
            if module_matches(imported, IMAGE_MATH_DEPS):
                violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_orjson_is_imported_only_through_json_tools() -> None:
    violations: list[str] = []
    for path in app_python_files():
        if path == JSON_TOOLS:
            continue
        for imported in imported_modules(path):
            if module_matches(imported, ("orjson",)):
                violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_rich_does_not_enter_backend_app_runtime() -> None:
    violations: list[str] = []
    for path in app_python_files():
        for imported in imported_modules(path):
            if module_matches(imported, ("rich",)):
                violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_image_math_does_not_import_domain_modules() -> None:
    violations: list[str] = []
    for path in image_math_python_files():
        for imported in imported_modules(path):
            if module_matches(imported, DOMAIN_IMPORT_PREFIXES):
                violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_image_math_does_not_contain_domain_decision_terms() -> None:
    violations: list[str] = []
    for path in image_math_python_files():
        text = path.read_text(encoding="utf-8")
        for term in DOMAIN_DECISION_STRINGS:
            if term in text:
                violations.append(f"{relative(path)} contains {term}")

    assert violations == []


def app_python_files() -> list[Path]:
    return sorted(path for path in APP_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def image_math_python_files() -> list[Path]:
    return sorted(path for path in IMAGE_MATH_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def module_matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def relative(path: Path) -> str:
    return str(path.relative_to(APP_ROOT.parent))
