# Plik: audyt_mw.py
# Wersja: 0.9.0
# Opis: Potrójny audyt kodu "MW" (Warsztat Menager) – szybki, głęboki i ryzyka.
#  - Przechodzi po katalogu projektu, skanuje pliki .py (i ważne .json)
#  - 3 przebiegi:
#       1) FAST: składnia, nagłówki (# Plik, # Wersja), zakazane wzorce
#       2) DEEP: AST – importy, graf zależności, cykle, zduplikowane definicje, proste unused imports
#       3) RISK: heurystyki miejsc ryzyka w GUI (tkinter), gołe excepty, eval/exec, wildcard importy
#  - Tworzy: audit_mw_report.json + audit_mw_report.md z wnioskami i sugestiami
#  - Opcjonalnie weryfikuje config.json, data/maszyny.json, uzytkownicy.json jeśli występują
# Użycie:
#   python audyt_mw.py "C:\\ścieżka\\do\\MW"
#   (bez argumentu – bierze bieżący katalog)

from __future__ import annotations
import os, re, sys, json, ast, traceback
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Tuple, Optional

HEADER_FILE_RE = re.compile(r"^#\s*Plik:\s*(?P<name>.+)$", re.IGNORECASE)
HEADER_VER_RE  = re.compile(r"^#\s*Wersja:\s*(?P<ver>.+)$", re.IGNORECASE)

FORBIDDEN_PATTERNS = [
    (re.compile(r"(^|\n)\s*from\s+[^\n]+\s+import\s+\*"), "Użycie 'from ... import *'"),
    (re.compile(r"(^|\n)\s*eval\s*\("), "Użycie eval()"),
    (re.compile(r"(^|\n)\s*exec\s*\("), "Użycie exec()"),
]

GUI_RISK_HINTS = [
    (re.compile(r"mainloop\s*\("), "Wywołanie mainloop() – upewnij się, że tylko jeden raz w całej aplikacji"),
    (re.compile(r"pack\(|grid\(|place\("), "Mieszanie pack/grid/place w tym samym kontenerze może powodować błędy layoutu"),
    (re.compile(r"after\(\s*\d+\s*,"), "Użycie .after(...) – sprawdź, czy nie gubi referencji i czy czyszczone przy zamykaniu"),
]

@dataclass
class FileIssue:
    file: str
    severity: str   # INFO/WARN/ERROR
    kind: str       # np. HEADER, SYNTAX, IMPORT, SECURITY, STYLE, JSON
    message: str
    line: Optional[int] = None

@dataclass
class FileSummary:
    file: str
    has_header_file: bool
    has_header_ver: bool
    declared_name: Optional[str]
    declared_ver: Optional[str]
    syntax_ok: bool
    defs: List[str]
    imports: List[str]

class AudytMW:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.py_files: List[str] = []
        self.json_files: List[str] = []
        self.issues: List[FileIssue] = []
        self.summaries: Dict[str, FileSummary] = {}
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.name_index: Dict[str, List[str]] = defaultdict(list)  # def name -> [files]

    # ---------- DISCOVERY ----------
    def discover(self):
        for dirpath, _, filenames in os.walk(self.root):
            # pomiń venv/venv-like, __pycache__ itp.
            if any(x in dirpath.replace("\\", "/").split("/") for x in ("__pycache__", ".git", ".venv", "venv", "env")):
                continue
            for fn in filenames:
                if fn.endswith('.py'):
                    self.py_files.append(os.path.join(dirpath, fn))
                elif fn.endswith('.json'):
                    self.json_files.append(os.path.join(dirpath, fn))
        self.py_files.sort()
        self.json_files.sort()

    # ---------- PASS 1: FAST ----------
    def pass_fast(self):
        for path in self.py_files:
            text = self._read(path)
            has_hf, has_hv, dname, dver = self._read_headers(text)
            syntax_ok, tree = self._parse_ast(path, text)

            imports, defs = [], []
            if tree:
                imports = self._collect_imports(tree)
                defs    = self._collect_defs(tree)

            self.summaries[path] = FileSummary(
                file=path, has_header_file=has_hf, has_header_ver=has_hv,
                declared_name=dname, declared_ver=dver, syntax_ok=syntax_ok,
                defs=defs, imports=imports,
            )

            if not has_hf:
                self._issue(path, 'WARN', 'HEADER', 'Brak nagłówka # Plik: ...')
            if not has_hv:
                self._issue(path, 'WARN', 'HEADER', 'Brak nagłówka # Wersja: ...')

            # nazwa w nagłówku vs faktyczna
            if has_hf and dname:
                base = os.path.basename(path)
                if dname.strip() != base:
                    self._issue(path, 'INFO', 'HEADER', f"Nagłówek # Plik wskazuje '{dname}', ale plik to '{base}'")

            # wzorce zabronione
            for regex, desc in FORBIDDEN_PATTERNS:
                for m in regex.finditer(text):
                    line = text.count('\n', 0, m.start()) + 1
                    self._issue(path, 'ERROR', 'SECURITY', f"{desc}", line)

            # hinty GUI
            for regex, desc in GUI_RISK_HINTS:
                for m in regex.finditer(text):
                    line = text.count('\n', 0, m.start()) + 1
                    self._issue(path, 'INFO', 'GUI', f"{desc}", line)

    # ---------- PASS 2: DEEP ----------
    def pass_deep(self):
        for path, summary in self.summaries.items():
            # graf importów (lokalne moduły)
            for imp in summary.imports:
                mod = imp.split('.')[0]
                # tylko lokalne: jeżeli istnieje {mod}.py w projekcie
                target_py = self._find_module_path(mod)
                if target_py:
                    self.import_graph[path].add(target_py)

            # indeks nazw
            for name in summary.defs:
                self.name_index[name].append(path)

        # cykle importów
        cycles = self._find_cycles()
        for cyc in cycles:
            self._issue(' :: '.join(cyc), 'WARN', 'IMPORT', 'Cykliczne importy (rozważ refaktor)')

        # zduplikowane definicje (heurystyka)
        for name, files in self.name_index.items():
            if len(set(files)) > 1 and name not in ('main'):
                self._issue(', '.join(sorted(set(files))), 'INFO', 'STYLE', f"Definicja '{name}' występuje w wielu plikach – rozważ prefiks albo wydzielenie wspólnego modułu")

        # proste unused imports (jeśli importowane, ale nieużyte nazwy)
        for path in self.py_files:
            text = self._read(path)
            try:
                tree = ast.parse(text)
            except Exception:
                continue
            imported_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
            used_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            unused = sorted(imported_names - used_names)
            for n in unused:
                self._issue(path, 'INFO', 'STYLE', f"Możliwy nieużyty import: {n}")

    # ---------- PASS 3: RISK ----------
    def pass_risk(self):
        for path in self.py_files:
            text = self._read(path)
            # gołe excepty
            for m in re.finditer(r"except\s*:\s*", text):
                line = text.count('\n', 0, m.start()) + 1
                self._issue(path, 'WARN', 'ERROR-HANDLING', 'Goły except – dodaj konkretny wyjątek i logowanie', line)
            # wyszukiwanie znaczników TODO/FIXME/HACK
            for m in re.finditer(r"\b(TODO|FIXME|HACK)\b", text):
                line = text.count('\n', 0, m.start()) + 1
                self._issue(path, 'INFO', 'TODO', 'Znacznik TODO/FIXME/HACK – rozważ zaplanowanie zadania', line)

        # JSON sanity
        self._check_json_file('config.json', required_keys=['theme', 'start_view', 'pin_required'])
        self._check_json_file('data/maszyny.json', required_keys=['id', 'nazwa', 'hala'])
        self._check_json_file('uzytkownicy.json', required_keys=['login', 'pin', 'rola'])

    # ---------- REPORT ----------
    def build_suggestions(self) -> List[str]:
        sug: List[str] = []
        # 1. Standaryzacja nagłówków
        missing_headers = [p for p,s in self.summaries.items() if not (s.has_header_file and s.has_header_ver)]
        if missing_headers:
            sug.append("Ujednolić nagłówki # Plik/# Wersja we wszystkich plikach (generator nagłówka w pre-commit).")
        # 2. Cykle importów
        if any(i.kind == 'IMPORT' and 'Cykliczne' in i.message for i in self.issues):
            sug.append("Rozbić cykliczne importy – wydzielić warstwę 'core' (modele, utils), 'gui' (widoki), 'app' (uruchomienie).")
        # 3. Bezpieczeństwo
        if any(i.kind == 'SECURITY' for i in self.issues):
            sug.append("Usunąć eval/exec i wildcard importy. Zastąpić bezpiecznymi fabrykami i jawnie importować symbole.")
        # 4. Obsługa błędów
        if any(i.kind == 'ERROR-HANDLING' for i in self.issues):
            sug.append("Zamienić gołe 'except' na konkretne wyjątki + logger z poziomami (info/warn/error).")
        # 5. GUI
        if any(i.kind == 'GUI' for i in self.issues):
            sug.append("Zapewnić pojedynczy mainloop, kontrolować .after() (cleanup przy zamknięciu), nie mieszać pack/grid w jednym kontenerze.")
        # 6. Styl i importy
        if any(i.kind == 'STYLE' for i in self.issues):
            sug.append("Dodać pre-commit (ruff + black, isort). Włączyć flake nieużytych importów.")
        # 7. JSON/konfiguracja
        if any(i.kind == 'JSON' for i in self.issues):
            sug.append("Walidować config.json/maszyny.json/uzytkownicy.json z JSON Schema na starcie aplikacji.")
        # 8. Architektura modułu serwisowego
        sug.append("Moduł serwisowy jako oddzielny pakiet z event-busem (pub/sub) i kolejką zadań – izolacja od GUI.")
        # 9. Potwierdzenia kasowania 3x
        sug.append("Potrójne potwierdzenie usuwania: dialog modalny z 3-krotnym 'OK' + timeout i klawisz ESC – antymisclick.")
        # 10. Spójny theme
        sug.append("Wydzielić ui_theme.py jako jedyne źródło kolorów/typografii; zakaz inline kolorów w GUI.")
        return sug

    def write_reports(self, out_json: str, out_md: str):
        data = {
            'root': self.root,
            'files_count': len(self.py_files),
            'issues': [asdict(i) for i in self.issues],
            'summaries': {k: asdict(v) for k,v in self.summaries.items()},
            'suggestions': self.build_suggestions(),
        }
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(out_md, 'w', encoding='utf-8') as f:
            f.write(self._render_md(data))

    # ---------- INTERNAL UTILS ----------
    def _read(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self._issue(path, 'ERROR', 'IO', f'Błąd czytania: {e}')
            return ''

    def _read_headers(self, text: str) -> Tuple[bool,bool,Optional[str],Optional[str]]:
        name = ver = None
        has_hf = has_hv = False
        for line in text.splitlines()[:15]:
            if not has_hf:
                m = HEADER_FILE_RE.match(line.strip())
                if m:
                    has_hf = True
                    name = m.group('name').strip()
            if not has_hv:
                m = HEADER_VER_RE.match(line.strip())
                if m:
                    has_hv = True
                    ver = m.group('ver').strip()
        return has_hf, has_hv, name, ver

    def _parse_ast(self, path: str, text: str) -> Tuple[bool, Optional[ast.AST]]:
        try:
            tree = ast.parse(text)
            return True, tree
        except SyntaxError as e:
            self._issue(path, 'ERROR', 'SYNTAX', f"{e.msg}", e.lineno or None)
            return False, None
        except Exception as e:
            self._issue(path, 'ERROR', 'SYNTAX', f"{e}")
            return False, None

    def _collect_imports(self, tree: ast.AST) -> List[str]:
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mods.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mods.append(node.module)
        return sorted(set(mods))

    def _collect_defs(self, tree: ast.AST) -> List[str]:
        names = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
        return sorted(set(names))

    def _find_module_path(self, module: str) -> Optional[str]:
        candidate = os.path.join(self.root, module + '.py')
        return candidate if os.path.exists(candidate) else None

    def _find_cycles(self) -> List[List[str]]:
        cycles = []
        color = {}
        stack = []
        def dfs(u: str):
            color[u] = 'grey'
            stack.append(u)
            for v in self.import_graph.get(u, []):
                if color.get(v) == 'grey':
                    # cycle found
                    idx = stack.index(v)
                    cycles.append(stack[idx:] + [v])
                elif color.get(v) != 'black':
                    dfs(v)
            color[u] = 'black'
            stack.pop()
        for node in list(self.import_graph.keys()):
            if color.get(node) is None:
                dfs(node)
        # skróć ścieżki do nazw plików
        short = []
        for cyc in cycles:
            short.append([os.path.relpath(x, self.root) for x in cyc])
        return short

    def _check_json_file(self, filename: str, required_keys: List[str]):
        path = os.path.join(self.root, filename)
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self._issue(path, 'ERROR', 'JSON', f'Błąd JSON: {e}')
            return
        # Dopuszczamy listę lub obiekt
        def check_obj(obj, idx=None):
            missing = [k for k in required_keys if k not in obj]
            if missing:
                where = f"[{idx}]" if idx is not None else ""
                self._issue(path, 'WARN', 'JSON', f"Brak kluczy {missing} w obiekcie {where}")
        if isinstance(data, list):
            for i, obj in enumerate(data):
                if isinstance(obj, dict):
                    check_obj(obj, i)
        elif isinstance(data, dict):
            check_obj(data)

    def _issue(self, file: str, severity: str, kind: str, message: str, line: Optional[int]=None):
        self.issues.append(FileIssue(file=file, severity=severity, kind=kind, message=message, line=line))

    def _render_md(self, data: Dict) -> str:
        lines = []
        lines.append(f"# Audyt MW – raport\n")
        lines.append(f"Katalog: {data['root']}\n")
        lines.append(f"Plików .py: {data['files_count']}\n")
        lines.append("\n## Sugestie\n")
        for s in data['suggestions']:
            lines.append(f"- {s}")
        lines.append("\n## Znalezione problemy\n")
        for i in data['issues']:
            loc = f":{i['line']}" if i['line'] else ""
            file_rel = os.path.relpath(i['file'], data['root']) if os.path.isabs(i['file']) else i['file']
            lines.append(f"- **{i['severity']}** [{i['kind']}] {file_rel}{loc} – {i['message']}")
        lines.append("\n## Podsumowania plików\n")
        for p, s in data['summaries'].items():
            file_rel = os.path.relpath(p, data['root']) if os.path.isabs(p) else p
            lines.append(f"### {file_rel}")
            lines.append(f"- Nagłówek # Plik: {'OK' if s['has_header_file'] else 'BRAK'}")
            lines.append(f"- Nagłówek # Wersja: {'OK' if s['has_header_ver'] else 'BRAK'}")
            if s['declared_name']:
                lines.append(f"- Deklarowana nazwa: {s['declared_name']}")
            if s['declared_ver']:
                lines.append(f"- Deklarowana wersja: {s['declared_ver']}")
            lines.append(f"- Składnia: {'OK' if s['syntax_ok'] else 'BŁĘDY'}")
            lines.append(f"- Importy: {', '.join(s['imports']) if s['imports'] else '-'}")
            lines.append(f"- Definicje: {', '.join(s['defs']) if s['defs'] else '-'}\n")
        return '\n'.join(lines)

# ---------- CLI ----------

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    audit = AudytMW(root)
    print(f"[MW] Audyt katalogu: {audit.root}")
    audit.discover()
    print(f"[PASS 1/3] FAST – składnia, nagłówki, wzorce...")
    audit.pass_fast()
    print(f"[PASS 2/3] DEEP – AST, graf importów, cykle...")
    audit.pass_deep()
    print(f"[PASS 3/3] RISK – heurystyki GUI, JSON...")
    audit.pass_risk()
    out_json = os.path.join(root, 'audit_mw_report.json')
    out_md   = os.path.join(root, 'audit_mw_report.md')
    audit.write_reports(out_json, out_md)
    print(f"[OK] Raporty zapisane: {out_json}, {out_md}")
    print("Skończone ✅")

if __name__ == '__main__':
    main()
