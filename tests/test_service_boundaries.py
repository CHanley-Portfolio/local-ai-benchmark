"""
Architecture-boundary tests for the standalone Benchmark Service.

These tests protect the repository separation between Local AI Benchmark and
Local AI Router. The Benchmark Service must remain independently installable
and must not import implementation packages owned by the router repository.
"""

import ast
from pathlib import Path

BENCHMARK_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "local_ai_benchmark"

FORBIDDEN_IMPORT_ROOTS = {
    "local_ai_router",
    "local_ai_inference",
}


def test_benchmark_service_does_not_import_router_packages() -> None:
    """
    Verify Benchmark Service source has no implementation dependency on router code.

    Python files are parsed through the abstract syntax tree rather than searched
    as plain text. This allows documentation to mention the Local AI Router where
    it is genuinely the subject of a benchmark without causing a false failure.
    """

    forbidden_imports: list[str] = []

    for python_file in BENCHMARK_SOURCE_ROOT.rglob("*.py"):
        syntax_tree = ast.parse(
            python_file.read_text(encoding="utf-8"),
            filename=str(python_file),
        )

        for syntax_node in ast.walk(syntax_tree):
            imported_modules: list[str] = []

            if isinstance(syntax_node, ast.Import):
                imported_modules.extend(imported_name.name for imported_name in syntax_node.names)

            elif isinstance(syntax_node, ast.ImportFrom):
                if syntax_node.module is not None:
                    imported_modules.append(syntax_node.module)

            for imported_module in imported_modules:
                import_root = imported_module.split(".", maxsplit=1)[0]

                if import_root in FORBIDDEN_IMPORT_ROOTS:
                    forbidden_imports.append(f"{python_file}: {imported_module}")

    assert forbidden_imports == [], (
        "Benchmark Service must not import packages owned by the "
        "Local AI Router repository:\n" + "\n".join(forbidden_imports)
    )
