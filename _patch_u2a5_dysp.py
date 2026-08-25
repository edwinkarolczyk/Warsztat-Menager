from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------
# dyspozycje_sources.py
# ---------------------------------------------------------------------
src_path = Path('dyspozycje_sources.py')
src = src_path.read_text(encoding='utf-8')
src = replace_once(src, '# version: 1.0\n', '# version: 1.1\n', 'sources version')
src = replace_once(
    src,
    '"""Źródła danych dla Dyspozycji (bez GUI)."""\n',
    '"""Źródła danych dla Dyspozycji (bez GUI)."""\n'
    '# Zmiany 1.1:\n'
    '# - Zlecenie wykonania korzysta z realnego Planowania oraz katalogów Produkt/Półprodukt.\n'
    '# - Dodano kontekst źródła: poziom wykonania, nr zlecenia, produkt i ilość.\n',
    'sources changelog',
)
start = src.index('def load_zlecenie_wykonania_choices() -> List[Tuple[str, str]]:')
new_tail = r'''def _read_json_dict(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _planowanie_file_path() -> str:
    return _data_path('planowanie', 'plan.json')


def _product_record(code: str) -> dict:
    path = os.path.join(_produkty_dir_path(), f'{code}.json')
    data = _read_json_dict(path)
    if not data:
        return {}
    return {
        'kod': str(data.get('kod') or data.get('symbol') or code).strip(),
        'nazwa': str(data.get('nazwa') or data.get('name') or '').strip(),
    }


def _semi_record(code: str) -> dict:
    path = os.path.join(_polprodukty_dir_path(), f'{code}.json')
    data = _read_json_dict(path)
    if not data:
        return {}
    return {
        'kod': str(data.get('kod') or data.get('id') or code).strip(),
        'nazwa': str(data.get('nazwa') or data.get('name') or '').strip(),
    }


def _plan_orders() -> list[dict]:
    data = _read_json_dict(_planowanie_file_path())
    rows = data.get('orders') or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def load_zlecenie_wykonania_choices() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    for row in _plan_orders():
        number = str(row.get('number') or '').strip()
        if not number:
            continue
        object_id = f'zlecenie:{number}'
        key = object_id.casefold()
        if key in seen:
            continue
        seen.add(key)
        product = str(row.get('product_code') or row.get('symbol') or '').strip()
        qty = row.get('qty', '')
        label = f'ZLECENIE {number}'
        if product:
            label += f' — {product}'
        if qty not in ('', None):
            label += f' × {qty}'
        out.append((object_id, label))

    for prefix, folder, label_prefix in (
        ('produkt', _produkty_dir_path(), 'PRODUKT'),
        ('polprodukt', _polprodukty_dir_path(), 'PÓŁPRODUKT'),
    ):
        try:
            names = sorted(os.listdir(folder))
        except Exception:
            names = []
        for filename in names:
            if not filename.lower().endswith('.json'):
                continue
            code = os.path.splitext(filename)[0].strip()
            if not code or code.lower() == 'bom':
                continue
            object_id = f'{prefix}:{code}'
            if object_id.casefold() in seen:
                continue
            seen.add(object_id.casefold())
            rec = _product_record(code) if prefix == 'produkt' else _semi_record(code)
            name = str(rec.get('nazwa') or '').strip()
            label = f'{label_prefix} — {code}' + (f' — {name}' if name else '')
            out.append((object_id, label))

    return out


def load_zlecenie_wykonania_context(object_id: str) -> dict:
    raw = str(object_id or '').strip()
    if ':' not in raw:
        return {}
    prefix, code = raw.split(':', 1)
    prefix = prefix.strip().lower()
    code = code.strip()
    if not code:
        return {}

    if prefix == 'zlecenie':
        for row in _plan_orders():
            number = str(row.get('number') or '').strip()
            if number.casefold() != code.casefold():
                continue
            product_code = str(row.get('product_code') or row.get('symbol') or '').strip()
            return {
                'poziom_wykonania': 'zlecenie',
                'nr_zlecenia': number,
                'order_id': str(row.get('id') or ''),
                'product_code': product_code,
                'ilosc_domyslna': row.get('qty', 1),
                'client': str(row.get('client') or ''),
            }
        return {'poziom_wykonania': 'zlecenie', 'nr_zlecenia': code, 'ilosc_domyslna': 1}

    if prefix == 'produkt':
        rec = _product_record(code)
        return {
            'poziom_wykonania': 'produkt',
            'product_code': str(rec.get('kod') or code),
            'product_name': str(rec.get('nazwa') or ''),
            'ilosc_domyslna': 1,
        }

    if prefix == 'polprodukt':
        rec = _semi_record(code)
        return {
            'poziom_wykonania': 'polprodukt',
            'polprodukt_code': str(rec.get('kod') or code),
            'polprodukt_name': str(rec.get('nazwa') or ''),
            'ilosc_domyslna': 1,
        }

    return {}
'''
src = src[:start] + new_tail
src_path.write_text(src, encoding='utf-8')


# ---------------------------------------------------------------------
# planowanie_magazyn.py - idempotent production surplus ledger
# ---------------------------------------------------------------------
wh_path = Path('planowanie_magazyn.py')
wh = wh_path.read_text(encoding='utf-8')
wh = replace_once(wh, '# version: 1.0\n', '# version: 1.1\n', 'warehouse bridge version')
wh = replace_once(
    wh,
    '# Most Planowanie <-> istniejący Magazyn. Nie tworzy równoległej bazy stanów.\n',
    '# Most Planowanie <-> istniejący Magazyn. Nie tworzy równoległej bazy stanów.\n'
    '# Zmiany 1.1: naddatek półproduktu może być księgowany idempotentnie po ID Dyspozycji.\n',
    'warehouse bridge changelog',
)
wh = replace_once(
    wh,
    'from typing import Any\n',
    'import json\nimport os\nfrom pathlib import Path\nfrom typing import Any\n',
    'warehouse imports',
)
wh = replace_once(
    wh,
    "def add_semiproduct_surplus(code: str, qty: float, *, name: str = '', user: str = '', context: str = '') -> dict[str, Any]:\n",
    "def _settlement_path() -> Path:\n"
    "    try:\n"
    "        from config_manager import ConfigManager\n"
    "        return Path(ConfigManager().path_data('magazyn', 'produkcja_rozliczenia.json'))\n"
    "    except Exception:\n"
    "        return Path('data') / 'magazyn' / 'produkcja_rozliczenia.json'\n\n"
    "def _load_settlements() -> dict[str, Any]:\n"
    "    path = _settlement_path()\n"
    "    try:\n"
    "        with path.open('r', encoding='utf-8') as handle:\n"
    "            data = json.load(handle)\n"
    "        return data if isinstance(data, dict) else {}\n"
    "    except Exception:\n"
    "        return {}\n\n"
    "def _save_settlements(data: dict[str, Any]) -> None:\n"
    "    path = _settlement_path()\n"
    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    "    tmp = path.with_suffix(path.suffix + '.tmp')\n"
    "    with tmp.open('w', encoding='utf-8') as handle:\n"
    "        json.dump(data, handle, ensure_ascii=False, indent=2)\n"
    "    os.replace(tmp, path)\n\n"
    "def add_semiproduct_surplus(code: str, qty: float, *, name: str = '', user: str = '', context: str = '', operation_id: str = '') -> dict[str, Any]:\n",
    'warehouse ledger helpers',
)
wh = replace_once(
    wh,
    "    if qty <= 0:\n        return {'kod': code, 'dodano': 0.0}\n",
    "    if qty <= 0:\n"
    "        return {'kod': code, 'dodano': 0.0}\n"
    "    operation_id = str(operation_id or '').strip()\n"
    "    if operation_id:\n"
    "        settlements = _load_settlements()\n"
    "        previous = settlements.get(operation_id)\n"
    "        if isinstance(previous, dict) and previous.get('status') == 'done':\n"
    "            return {'kod': code, 'dodano': 0.0, 'already_settled': True, 'previous': previous}\n",
    'warehouse operation guard',
)
wh = replace_once(
    wh,
    "    return {'kod': code, 'dodano': qty, 'stan': _num((saved or {}).get('stan'))}\n",
    "    result = {'kod': code, 'dodano': qty, 'stan': _num((saved or {}).get('stan'))}\n"
    "    if operation_id:\n"
    "        settlements = _load_settlements()\n"
    "        settlements[operation_id] = {\n"
    "            'status': 'done', 'kod': code, 'ilosc': qty, 'user': str(user or ''), 'context': str(context or '')\n"
    "        }\n"
    "        _save_settlements(settlements)\n"
    "    return result\n",
    'warehouse ledger save',
)
wh_path.write_text(wh, encoding='utf-8')


# ---------------------------------------------------------------------
# gui_dyspozycje_creator.py
# ---------------------------------------------------------------------
creator_path = Path('gui_dyspozycje_creator.py')
creator = creator_path.read_text(encoding='utf-8')
creator = replace_once(creator, '# version: 1.2\n', '# version: 1.3\n', 'creator version')
creator = replace_once(
    creator,
    '# Zmiany 1.2:\n',
    '# Zmiany 1.3:\n'
    '# - Zlecenie wykonania wybiera realne Zlecenie, Produkt albo Półprodukt i ilość do wykonania.\n'
    '# - Dyspozycja zapisuje nr zlecenia/poziom wykonania oraz podgląd zapotrzebowania z Magazynu.\n'
    '# - Wyszukiwarka działa również dla źródeł wykonania.\n'
    '# Zmiany 1.2:\n',
    'creator changelog',
)
creator = replace_once(
    creator,
    '    load_zlecenie_wykonania_choices,\n',
    '    load_zlecenie_wykonania_choices,\n    load_zlecenie_wykonania_context,\n',
    'creator context import',
)
creator = replace_once(
    creator,
    "    cb_object.grid(row=3, column=1, sticky=\"ew\", pady=4)\n",
    "    cb_object.grid(row=3, column=1, sticky=\"ew\", pady=4)\n\n"
    "    var_exec_qty = tk.StringVar(value=str(((ctx.get('meta') or {}).get('ilosc_do_wykonania') if isinstance(ctx.get('meta'), dict) else '') or '1'))\n"
    "    exec_qty_frame = ttk.Frame(frame)\n"
    "    exec_qty_frame.grid(row=3, column=2, sticky=\"w\", padx=(10, 0), pady=4)\n"
    "    ttk.Label(exec_qty_frame, text=\"Ilość do wykonania:\").pack(side=\"left\")\n"
    "    ent_exec_qty = ttk.Entry(exec_qty_frame, textvariable=var_exec_qty, width=12)\n"
    "    ent_exec_qty.pack(side=\"left\", padx=(6, 0))\n"
    "    exec_qty_frame.grid_remove()\n",
    'creator execution qty',
)
creator = replace_once(
    creator,
    "    options_map: dict[str, str] = {}\n    all_labels: list[str] = []\n    source_module = {\"value\": \"\"}\n",
    "    options_map: dict[str, str] = {}\n"
    "    all_labels: list[str] = []\n"
    "    source_module = {\"value\": \"\"}\n"
    "    execution_context = {\"value\": {}}\n"
    "    execution_qty_touched = {\"value\": False}\n",
    'creator execution state',
)
creator = replace_once(
    creator,
    "    if not edit_mode:\n        object_panel.grid_remove()\n",
    "    if not edit_mode:\n        object_panel.grid_remove()\n\n"
    "    def _execution_requirements(object_id: str, qty_value: str):\n"
    "        ctx_exec = load_zlecenie_wykonania_context(object_id) or {}\n"
    "        try:\n"
    "            qty = float(str(qty_value or '1').replace(',', '.'))\n"
    "        except (TypeError, ValueError):\n"
    "            return ctx_exec, None\n"
    "        try:\n"
    "            from produkty_store import ProductCatalog\n"
    "            from polprodukty_store import SemiProductCatalog\n"
    "            from planowanie_zapotrzebowanie import RequirementCalculator\n"
    "            pc = ProductCatalog()\n"
    "            calc = RequirementCalculator(pc, SemiProductCatalog(pc.cfg))\n"
    "            level = str(ctx_exec.get('poziom_wykonania') or '')\n"
    "            if level == 'zlecenie':\n"
    "                result = calc.calculate_with_stock(str(ctx_exec.get('product_code') or ''), qty)\n"
    "            elif level == 'produkt':\n"
    "                result = calc.calculate_with_stock(str(ctx_exec.get('product_code') or ''), qty)\n"
    "            elif level == 'polprodukt':\n"
    "                result = calc.calculate_semi_with_stock(str(ctx_exec.get('polprodukt_code') or ''), qty, ignore_root_stock=True)\n"
    "            else:\n"
    "                result = None\n"
    "        except Exception:\n"
    "            result = None\n"
    "        return ctx_exec, result\n",
    'creator execution helper',
)
creator = replace_once(
    creator,
    "        else:\n            var_object_panel_info.set(\n                \"Dla tego typu dyspozycji nie ma jeszcze edytora \"\n                \"kontekstowego w dolnym panelu.\"\n            )\n",
    "        elif typ == 'zlecenie_wykonania':\n"
    "            object_panel.grid()\n"
    "            ctx_exec, req = _execution_requirements(object_id, var_exec_qty.get())\n"
    "            execution_context['value'] = ctx_exec\n"
    "            level = str(ctx_exec.get('poziom_wykonania') or 'wykonanie')\n"
    "            preview = {\n"
    "                'Poziom': level,\n"
    "                'Nr zlecenia': str(ctx_exec.get('nr_zlecenia') or '—'),\n"
    "                'Produkt': str(ctx_exec.get('product_code') or '—'),\n"
    "                'Półprodukt': str(ctx_exec.get('polprodukt_code') or '—'),\n"
    "                'Ilość do wykonania': var_exec_qty.get(),\n"
    "            }\n"
    "            if isinstance(req, dict):\n"
    "                shortages = []\n"
    "                for row in req.get('rows') or []:\n"
    "                    try:\n"
    "                        missing = float(row.get('brak') or 0)\n"
    "                    except (TypeError, ValueError):\n"
    "                        missing = 0\n"
    "                    if missing > 0:\n"
    "                        shortages.append(f\"{row.get('typ','')} {row.get('kod','')}: {missing:g} {row.get('jednostka','')}\")\n"
    "                preview['Braki / do wykonania'] = '\\n'.join(shortages[:18]) if shortages else 'Brak braków wg bieżącego Magazynu'\n"
    "            var_object_panel_info.set('Wykonanie powiązane z Planowaniem i bieżącym stanem Magazynu.')\n"
    "            _render_object_card('Wykonanie produkcyjne', preview)\n"
    "        else:\n"
    "            if not edit_mode:\n"
    "                object_panel.grid_remove()\n"
    "            var_object_panel_info.set(\n"
    "                \"Dla tego typu dyspozycji nie ma jeszcze edytora \"\n"
    "                \"kontekstowego w dolnym panelu.\"\n"
    "            )\n",
    'creator execution preview',
)
creator = replace_once(
    creator,
    "        if source_key in {\"narzedzia\", \"maszyny\"}:\n",
    "        if source_key in {\"narzedzia\", \"maszyny\", \"zlecenia\"}:\n",
    'creator search source show',
)
creator = replace_once(
    creator,
    "        var_object_display.set(picked)\n        _refresh_object_panel()\n",
    "        var_object_display.set(picked)\n"
    "        if source_key == 'zlecenia':\n"
    "            exec_qty_frame.grid()\n"
    "            selected_id = options_map.get(picked, '')\n"
    "            selected_ctx = load_zlecenie_wykonania_context(selected_id) or {}\n"
    "            execution_context['value'] = selected_ctx\n"
    "            if not edit_mode and not execution_qty_touched['value']:\n"
    "                var_exec_qty.set(str(selected_ctx.get('ilosc_domyslna') or 1))\n"
    "        else:\n"
    "            exec_qty_frame.grid_remove()\n"
    "        _refresh_object_panel()\n",
    'creator qty source refresh',
)
creator = replace_once(
    creator,
    "        if source_module[\"value\"] not in {\"narzedzia\", \"maszyny\"}:\n",
    "        if source_module[\"value\"] not in {\"narzedzia\", \"maszyny\", \"zlecenia\"}:\n",
    'creator search filter source',
)
creator = replace_once(
    creator,
    "    var_object_search.trace_add(\"write\", _filter_objects)\n    cb_object.bind(\"<<ComboboxSelected>>\", _refresh_object_panel)\n",
    "    def _mark_exec_qty(*_args):\n"
    "        execution_qty_touched['value'] = True\n"
    "        if var_type.get().strip().lower() == 'zlecenie_wykonania':\n"
    "            _refresh_object_panel()\n\n"
    "    var_exec_qty.trace_add('write', _mark_exec_qty)\n"
    "    var_object_search.trace_add(\"write\", _filter_objects)\n"
    "    cb_object.bind(\"<<ComboboxSelected>>\", _refresh_object_panel)\n",
    'creator qty trace',
)
creator = replace_once(
    creator,
    "    def _close_current() -> None:\n        if not edit_mode or not existing_id:\n            return\n",
    "    def _close_current() -> None:\n"
    "        if not edit_mode or not existing_id:\n"
    "            return\n"
    "        if var_type.get().strip().lower() == 'zlecenie_wykonania':\n"
    "            messagebox.showinfo(\n"
    "                'Dyspozycje',\n"
    "                'Dyspozycję wykonania zamknij z głównej listy Dyspozycji. Tam WM rozliczy ilość wykonaną i naddatek półproduktu.',\n"
    "                parent=win,\n"
    "            )\n"
    "            return\n",
    'creator block direct production close',
)
old_payload = '''        title = str(ctx.get("tytul") or "").strip() or selected_label or var_type.get().strip()
        payload = {
            "typ_dyspozycji": var_type.get().strip(),
            "tytul": title,
            "opis": txt_desc.get("1.0", "end").strip(),
            "autor": _actor_login(),
            "przypisane_do": assigned,
            "dla_wszystkich": for_all,
            "termin": deadline_iso,
            "priorytet": var_priority.get().strip(),
            "modul_zrodlowy": source_module["value"],
            "obiekt_id": object_id,
            "meta": {"object_label": selected_label},
        }
'''
new_payload = '''        meta_payload = dict(ctx.get("meta") or {}) if isinstance(ctx.get("meta"), dict) else {}
        meta_payload["object_label"] = selected_label
        exec_level = ""
        if var_type.get().strip().lower() == "zlecenie_wykonania":
            try:
                exec_qty = float(var_exec_qty.get().strip().replace(",", "."))
            except ValueError:
                messagebox.showwarning("Dyspozycje", "Ilość do wykonania musi być liczbą.", parent=win)
                return
            if exec_qty <= 0:
                messagebox.showwarning("Dyspozycje", "Ilość do wykonania musi być większa od zera.", parent=win)
                return
            if exec_qty.is_integer():
                exec_qty = int(exec_qty)
            exec_ctx, req = _execution_requirements(object_id, str(exec_qty))
            meta_payload.update(exec_ctx)
            meta_payload["ilosc_do_wykonania"] = exec_qty
            exec_level = str(exec_ctx.get("poziom_wykonania") or "")
            if isinstance(req, dict):
                meta_payload["zapotrzebowanie"] = list(req.get("rows") or [])
                meta_payload["zapotrzebowanie_uwagi"] = list(req.get("warnings") or [])

        title = str(ctx.get("tytul") or "").strip()
        if not title and var_type.get().strip().lower() == "zlecenie_wykonania":
            if exec_level == "zlecenie":
                title = f"Wykonaj Zlecenie {meta_payload.get('nr_zlecenia') or ''}".strip()
            elif exec_level == "produkt":
                title = f"Wykonaj produkt {meta_payload.get('product_code') or ''}".strip()
            elif exec_level == "polprodukt":
                title = f"Wykonaj półprodukt {meta_payload.get('polprodukt_code') or ''}".strip()
        title = title or selected_label or var_type.get().strip()
        payload = {
            "typ_dyspozycji": var_type.get().strip(),
            "tytul": title,
            "opis": txt_desc.get("1.0", "end").strip(),
            "autor": _actor_login(),
            "przypisane_do": assigned,
            "dla_wszystkich": for_all,
            "termin": deadline_iso,
            "priorytet": var_priority.get().strip(),
            "modul_zrodlowy": source_module["value"],
            "obiekt_id": object_id,
            "meta": meta_payload,
        }
'''
creator = replace_once(creator, old_payload, new_payload, 'creator save production meta')
creator_path.write_text(creator, encoding='utf-8')


# ---------------------------------------------------------------------
# gui_zlecenia.py - production completion and surplus settlement
# ---------------------------------------------------------------------
dysp_ui_path = Path('gui_zlecenia.py')
dysp_ui = dysp_ui_path.read_text(encoding='utf-8')
dysp_ui = replace_once(dysp_ui, '# version: 1.4\n', '# version: 1.5\n', 'dysp ui version')
dysp_ui = replace_once(
    dysp_ui,
    '# Zmiany 1.4:\n',
    '# Zmiany 1.5:\n'
    '# - Zamknięcie Dyspozycji wykonania zapisuje faktyczną ilość wykonaną.\n'
    '# - Dla półproduktu naddatek ponad plan automatycznie zwiększa stan Magazynu.\n'
    '# - Rozliczenie naddatku jest chronione przed podwójnym zaksięgowaniem po ID Dyspozycji.\n'
    '# Zmiany 1.4:\n',
    'dysp ui changelog',
)
dysp_ui = replace_once(
    dysp_ui,
    '    set_dyspozycja_status,\n',
    '    set_dyspozycja_status,\n    update_dyspozycja,\n',
    'dysp update import',
)
dysp_ui = replace_once(
    dysp_ui,
    'from services.profile_service import ProfileService\n',
    'from services.profile_service import ProfileService\n'
    'from planowanie_magazyn import WarehouseIntegrationError, add_semiproduct_surplus\n',
    'dysp warehouse import',
)
old_close_mid = '''        who = self._login_user or str(mapped.get("autor") or "").strip()
        changed = set_dyspozycja_status(
            dysp_id,
            "zamknieta",
            changed_by=who,
            uwagi=note or "",
        )
'''
new_close_mid = '''        who = self._login_user or str(mapped.get("autor") or "").strip()
        typ = str(mapped.get("typ_dyspozycji") or "").strip().lower()
        if typ == "zlecenie_wykonania":
            meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
            try:
                planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
            except (TypeError, ValueError):
                planned = 0.0
            actual = simpledialog.askfloat(
                "Rozlicz wykonanie",
                "Ile faktycznie wykonano?",
                initialvalue=planned if planned > 0 else 1,
                minvalue=0.0,
                parent=self,
            )
            if actual is None:
                return
            meta["ilosc_wykonana"] = actual
            meta["brak_wykonania"] = max(0.0, planned - actual)
            level = str(meta.get("poziom_wykonania") or "").strip().lower()
            if level == "polprodukt":
                surplus = max(0.0, actual - planned)
                meta["naddatek"] = surplus
                if surplus > 0:
                    code = str(meta.get("polprodukt_code") or "").strip()
                    name = str(meta.get("polprodukt_name") or code)
                    try:
                        result = add_semiproduct_surplus(
                            code,
                            surplus,
                            name=name,
                            user=who,
                            context=f"Dyspozycja {dysp_id}",
                            operation_id=dysp_id,
                        )
                    except WarehouseIntegrationError as exc:
                        messagebox.showerror(
                            "Rozliczenie produkcji",
                            f"Nie udało się zaksięgować naddatku w Magazynie:\n{exc}\n\nDyspozycja nie została zamknięta.",
                            parent=self,
                        )
                        return
                    meta["naddatek_zaksiegowany"] = bool(result.get("dodano") or result.get("already_settled"))
            updated = update_dyspozycja(dysp_id, {"meta": meta})
            if updated:
                mapped = updated

        changed = set_dyspozycja_status(
            dysp_id,
            "zamknieta",
            changed_by=who,
            uwagi=note or "",
        )
'''
dysp_ui = replace_once(dysp_ui, old_close_mid, new_close_mid, 'dysp production close')
dysp_ui_path.write_text(dysp_ui, encoding='utf-8')


# ---------------------------------------------------------------------
# gui_planowanie.py - brygadzista can operate planning + direct disposition shortcut
# ---------------------------------------------------------------------
plan_path = Path('gui_planowanie.py')
plan = plan_path.read_text(encoding='utf-8')
plan = replace_once(plan, '# version: 1.5\n', '# version: 1.6\n', 'planning version')
plan = replace_once(
    plan,
    '# Zmiany 1.5:\n',
    '# Zmiany 1.6:\n'
    '# - Brygadzista może tworzyć i edytować Zlecenia w Planowaniu zgodnie z rolą projektu.\n'
    '# - Z wybranego Zlecenia można otworzyć kreator Dyspozycji wykonania z gotowym kontekstem.\n'
    '# Zmiany 1.5:\n',
    'planning changelog',
)
plan = replace_once(
    plan,
    '        can_edit = self.role in EDIT_ROLES or self.is_manager\n',
    '        can_edit = self.role in EDIT_ROLES or self.is_manager or self.is_bryg\n',
    'planning bryg permissions',
)
plan = replace_once(
    plan,
    '        ttk.Button(top, text="Archiwum", command=self._archive_selected_order).pack(side="left", padx=3)\n',
    '        ttk.Button(top, text="Archiwum", command=self._archive_selected_order).pack(side="left", padx=3)\n'
    '        ttk.Button(top, text="Dyspozycja wykonania", command=self._create_execution_disposition).pack(side="left", padx=(8, 3))\n',
    'planning dysp button',
)
plan = replace_once(
    plan,
    '    def _show_order_detail(self):\n',
    '    def _create_execution_disposition(self):\n'
    '        order = self._selected_order()\n'
    '        if not order:\n'
    '            messagebox.showinfo("Planowanie", "Najpierw wybierz zlecenie.", parent=self.root)\n'
    '            return\n'
    '        number = str(order.get("number") or "").strip()\n'
    '        if not number:\n'
    '            return\n'
    '        try:\n'
    '            from gui_dyspozycje_creator import open_dyspozycje_creator\n'
    '            open_dyspozycje_creator(\n'
    '                self.frame,\n'
    '                autor=str(self.login or ""),\n'
    '                context={\n'
    '                    "typ_dyspozycji": "zlecenie_wykonania",\n'
    '                    "obiekt_id": f"zlecenie:{number}",\n'
    '                    "modul_zrodlowy": "planowanie",\n'
    '                },\n'
    '            )\n'
    '        except Exception as exc:\n'
    '            messagebox.showerror("Planowanie", f"Nie udało się otworzyć Dyspozycji wykonania:\\n{exc}", parent=self.root)\n\n'
    '    def _show_order_detail(self):\n',
    'planning create dysp method',
)
plan_path.write_text(plan, encoding='utf-8')

print('U2A-5 production dispositions patch prepared')
