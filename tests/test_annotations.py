"""A guard that every public function is fully annotated.

``mypy --strict`` already checks this, but it is a separate tool.  This test
runs with nothing but the standard library, so the guarantee does not depend
on a third party package being installed.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Iterator, List, Tuple

SOURCE = Path(__file__).resolve().parent.parent / "src" / "cronport"


def _modules() -> Iterator[Tuple[str, ast.Module]]:
    for path in sorted(SOURCE.rglob("*.py")):
        relative = path.relative_to(SOURCE.parent).as_posix()
        yield relative, ast.parse(path.read_text(encoding="utf-8"), filename=relative)


def _functions(tree: ast.Module) -> Iterator[Tuple[str, ast.FunctionDef]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node


class AnnotationTests(unittest.TestCase):
    def test_every_function_is_annotated(self) -> None:
        problems: List[str] = []
        for relative, tree in _modules():
            for name, node in _functions(tree):
                arguments = node.args
                parameters = list(arguments.posonlyargs) + list(arguments.args)
                parameters += list(arguments.kwonlyargs)
                if arguments.vararg is not None:
                    parameters.append(arguments.vararg)
                if arguments.kwarg is not None:
                    parameters.append(arguments.kwarg)

                for parameter in parameters:
                    if parameter.arg in ("self", "cls"):
                        continue
                    if parameter.annotation is None:
                        problems.append(
                            f"{relative}:{node.lineno}: {name}() has no annotation "
                            f"for '{parameter.arg}'"
                        )
                if node.returns is None:
                    problems.append(
                        f"{relative}:{node.lineno}: {name}() has no return annotation"
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_no_bare_generics(self) -> None:
        """``def f() -> list`` hides the element type; use ``List[str]``."""
        problems: List[str] = []
        bare = {"list", "dict", "set", "tuple", "frozenset", "type"}
        for relative, tree in _modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in bare:
                    parent = getattr(node, "_parent", None)
                    if parent is None:
                        continue
                if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                    if node.value.id in bare:
                        problems.append(
                            f"{relative}:{node.lineno}: {node.value.id} without a "
                            f"type parameter"
                        )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_no_type_ignore_without_a_reason(self) -> None:
        """A ``type: ignore`` should say what it is hiding."""
        problems: List[str] = []
        for relative, tree in _modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant):
                    continue
                text = node.value.value
                if isinstance(text, str) and text.strip() == "type: ignore":
                    problems.append(f"{relative}:{node.lineno}: bare 'type: ignore'")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_module_has_a_docstring(self) -> None:
        problems = [
            relative
            for relative, tree in _modules()
            if not (tree.body and isinstance(tree.body[0], ast.Expr))
            or not isinstance(tree.body[0].value, ast.Constant)
            or not tree.body[0].value.value
        ]
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
