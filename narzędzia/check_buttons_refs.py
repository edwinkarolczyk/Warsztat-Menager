# version: 1.0
# WM-VERSION: 0.1
"""Static checker for Tkinter buttons ensuring ``command`` callbacks exist."""

from __future__ import annotations

import argparse
import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "tests",
}
BUTTON_ATTR = "Button"
CONFIG_METHODS = {"config", "configure"}
DEFAULT_REPORT = Path("reports/buttons_report.md")


@dataclass
class ButtonRecord:
    file: Path
    lineno: int
    col: int
    names: List[str]
    command_repr: Optional[str]
    direct_empty: bool
    configure_commands: List[Tuple[int, str]] = field(default_factory=list)
    configure_empty: List[int] = field(default_factory=list)

    @property
    def primary_name(self) -> str:
        return self.names[0] if self.names else "<anon>"

    @property
    def has_valid_command(self) -> bool:
        if self.command_repr and not self.direct_empty:
            return True
        return bool(self.configure_commands)

    def register_configure(self, line: int, value_repr: Optional[str], is_empty: bool) -> None:
        if is_empty:
            self.configure_empty.append(line)
        elif value_repr is not None:
            self.configure_commands.append((line, value_repr))


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    file: Path
    line: int
    name: str
    message: str


class ButtonAnalyzer(ast.NodeVisitor):
    def __init__(self, path: Path, source: str) -> None:
        self.path = path
        self.source = source
        self.entries: List[ButtonRecord] = []
        self._name_to_entries: Dict[str, List[ButtonRecord]] = {}
        self._pending_configures: Dict[str, List[Tuple[int, Optional[str], bool]]] = {}

    # --- Visitor methods -------------------------------------------------
    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: D401 - ast visitor
        if self._record_button(node.value, node.targets):
            return
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: D401
        target = [node.target] if node.target is not None else []
        if self._record_button(node.value, target):
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: D401
        if self._handle_configure(node):
            self.generic_visit(node)
            return

        if getattr(node, "_wm_recorded", False):
            self.generic_visit(node)
            return

        if self._is_button_call(node.func):
            self._register_record(self._build_record(node, []))
            node._wm_recorded = True  # type: ignore[attr-defined]

        self.generic_visit(node)

    # --- Helpers ---------------------------------------------------------
    def _build_record(self, call: ast.Call, targets: Iterable[ast.expr]) -> ButtonRecord:
        names = [expr for target in targets for expr in self._extract_names(target)]
        command_repr, is_empty = self._command_argument(call)
        record = ButtonRecord(
            file=self.path,
            lineno=call.lineno,
            col=call.col_offset,
            names=names,
            command_repr=command_repr,
            direct_empty=is_empty,
        )
        return record

    def _register_record(self, record: ButtonRecord) -> None:
        self.entries.append(record)
        for name in record.names:
            self._name_to_entries.setdefault(name, []).append(record)
            pending = self._pending_configures.pop(name, [])
            for line, value_repr, is_empty in pending:
                record.register_configure(line, value_repr, is_empty)

    def _record_button(self, value: Optional[ast.AST], targets: Iterable[ast.expr]) -> bool:
        if isinstance(value, ast.Call) and self._is_button_call(value.func):
            record = self._build_record(value, targets)
            self._register_record(record)
            value._wm_recorded = True  # type: ignore[attr-defined]
            return True

        if isinstance(value, ast.GeneratorExp) and isinstance(value.elt, ast.Call):
            call = value.elt
            if self._is_button_call(call.func):
                record = self._build_record(call, targets)
                self._register_record(record)
                call._wm_recorded = True  # type: ignore[attr-defined]
                return True

        return False

    def _command_argument(self, call: ast.Call) -> Tuple[Optional[str], bool]:
        for keyword in call.keywords:
            if keyword.arg == "command":
                value_repr = ast.get_source_segment(self.source, keyword.value)
                if value_repr is None:
                    value_repr = ast.unparse(keyword.value)
                is_empty = _is_empty_command(keyword.value)
                return value_repr, is_empty
        return None, False

    def _handle_configure(self, node: ast.Call) -> bool:
        func = node.func
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr not in CONFIG_METHODS:
            return False

        has_command = False
        value_repr: Optional[str] = None
        is_empty = False
        for keyword in node.keywords:
            if keyword.arg == "command":
                has_command = True
                value_repr = ast.get_source_segment(self.source, keyword.value)
                if value_repr is None:
                    value_repr = ast.unparse(keyword.value)
                is_empty = _is_empty_command(keyword.value)
                break

        if not has_command:
            return False

        target_name = self._expr_to_name(func.value)
        if not target_name:
            return True

        entries = self._name_to_entries.get(target_name)
        if entries:
            for entry in entries:
                entry.register_configure(node.lineno, value_repr, is_empty)
        else:
            self._pending_configures.setdefault(target_name, []).append(
                (node.lineno, value_repr, is_empty)
            )
        return True

    def _is_button_call(self, func: ast.AST) -> bool:
        if isinstance(func, ast.Name):
            return func.id.endswith(BUTTON_ATTR)
        if isinstance(func, ast.Attribute):
            return func.attr == BUTTON_ATTR
        return False

    def _extract_names(self, target: ast.expr) -> List[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Attribute):
            name = self._expr_to_name(target)
            return [name] if name else []
        if isinstance(target, (ast.Tuple, ast.List)):
            names: List[str] = []
            for element in target.elts:
                names.extend(self._extract_names(element))
            return names
        if isinstance(target, ast.Subscript):
            name = self._expr_to_name(target)
            return [name] if name else []
        return []

    def _expr_to_name(self, expr: ast.AST) -> Optional[str]:
        try:
            return ast.unparse(expr)
        except Exception:  # pragma: no cover - defensive
            return None


def _is_empty_command(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value in (None, "", False)
    return False


def iter_python_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def analyze_file(path: Path) -> List[ButtonRecord]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    analyzer = ButtonAnalyzer(path, source)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    analyzer.visit(tree)
    return analyzer.entries


def collect_issues(records: List[ButtonRecord]) -> List[Issue]:
    issues: List[Issue] = []
    for record in records:
        if not record.has_valid_command:
            issues.append(
                Issue(
                    severity="error",
                    file=record.file,
                    line=record.lineno,
                    name=record.primary_name,
                    message="Brak parametru command dla przycisku.",
                )
            )
        if record.direct_empty:
            issues.append(
                Issue(
                    severity="warning",
                    file=record.file,
                    line=record.lineno,
                    name=record.primary_name,
                    message="Parametr command ustawiono na pustą wartość.",
                )
            )
        for line in record.configure_empty:
            issues.append(
                Issue(
                    severity="warning",
                    file=record.file,
                    line=line,
                    name=record.primary_name,
                    message="configure(command=...) ustawione na pustą wartość.",
                )
            )
    return issues


def render_report(
    root: Path,
    files: List[Path],
    records: List[ButtonRecord],
    issues: List[Issue],
) -> str:
    total_buttons = len(records)
    problems = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")

    lines = [
        "# Raport kontroli przycisków",
        "",
        f"- Katalog skanowania: {root.resolve()}",
        f"- Przetworzonych plików: {len(files)}",
        f"- Liczba przycisków: {total_buttons}",
        f"- Problemy: {problems}",
        f"- Ostrzeżenia: {warnings}",
        "",
    ]

    if issues:
        lines.append("## Szczegóły problemów")
        lines.append("")
        lines.append("| Poziom | Plik | Linia | Nazwa | Opis |")
        lines.append("| --- | --- | --- | --- | --- |")
        for issue in sorted(
            issues,
            key=lambda item: (0 if item.severity == "error" else 1, str(item.file), item.line),
        ):
            try:
                rel_path = issue.file.relative_to(root)
            except ValueError:
                rel_path = issue.file
            lines.append(
                f"| {issue.severity.upper()} | {rel_path.as_posix()} | {issue.line} | {issue.name} | {issue.message} |"
            )
    else:
        lines.append("Brak problemów. ✅ Wszystkie przyciski posiadają przypisane akcje.")

    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sprawdź definicje przycisków Tkinter.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Katalog startowy skanowania.")
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Ścieżka docelowa raportu w formacie Markdown.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    files = sorted(iter_python_files(root))
    records: List[ButtonRecord] = []
    for file_path in files:
        records.extend(analyze_file(file_path))

    issues = collect_issues(records)
    report_text = render_report(root, files, records, issues)

    report_path = args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    print(f"Raport zapisano: {report_path}")
    print(f"Łącznie przycisków: {len(records)}, problemy: {sum(1 for i in issues if i.severity == 'error')}, ostrzeżenia: {sum(1 for i in issues if i.severity == 'warning')}")

    return 0 if all(issue.severity != "error" for issue in issues) else 1


if __name__ == "__main__":
    raise SystemExit(main())
