import ast
from pathlib import Path
import tomllib


PRODUCT_PACKAGE = Path(__file__).parents[1] / "src" / "silemio_control_hub"
FORBIDDEN_PACKAGE = "ec4lpbridge"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_product_core_never_imports_the_historical_bridge_package():
    violations = {
        str(path.relative_to(PRODUCT_PACKAGE)): sorted(
            module
            for module in _imported_modules(path)
            if module == FORBIDDEN_PACKAGE
            or module.startswith(f"{FORBIDDEN_PACKAGE}.")
        )
        for path in PRODUCT_PACKAGE.rglob("*.py")
    }
    violations = {path: modules for path, modules in violations.items() if modules}

    assert violations == {}


def test_distribution_contains_only_the_independent_product_package():
    project = tomllib.loads(
        (PRODUCT_PACKAGE.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert project["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "silemio_control_hub*"
    ]
    assert "ec4-liveprofessor-legacy" not in project["project"]["scripts"]
