# version: 1.0


def test_new_planista_raw_form_keeps_first_row():
    from rc1_magazyn_fix import _remove_manual_raw_name_row

    class Owner:
        s_vars = {"rodzaj": object(), "rozmiar": object()}

    class Parent:
        def winfo_children(self):
            raise AssertionError("Nowy formularz nie powinien usuwać żadnego wiersza")

    assert _remove_manual_raw_name_row(Owner(), Parent()) is False


def test_magazyn_columns_are_grouped_for_reading():
    from rc1_magazyn_fix import _apply_magazyn_column_layout

    original = (
        "id", "sekcja", "typ", "rozmiar", "nazwa", "stan",
        "rezerwacje", "dostepne", "jednostka", "lokalizacja", "zadania",
    )

    class Tree:
        def __init__(self):
            self.displaycolumns = None
            self.widths = {}

        def __getitem__(self, key):
            assert key == "columns"
            return original

        def configure(self, **kwargs):
            self.displaycolumns = tuple(kwargs["displaycolumns"])

        def column(self, name, **kwargs):
            self.widths[name] = kwargs

    class Owner:
        tree = Tree()

    owner = Owner()
    assert _apply_magazyn_column_layout(owner) is True
    assert owner.tree.displaycolumns == (
        "id",
        "nazwa",
        "rozmiar",
        "stan",
        "rezerwacje",
        "dostepne",
        "jednostka",
        "lokalizacja",
        "zadania",
        "typ",
        "sekcja",
    )


def test_machine_cards_path_uses_active_windows_root(monkeypatch):
    from machine_card_root_runtime import machine_cards_output_path

    monkeypatch.setenv("WM_ROOT", r"C:\folder wm")
    assert machine_cards_output_path("wydruki", "karty") == (
        r"C:\folder wm\wydruki\karty"
    )


def test_machine_cards_path_patch_targets_cards_only(monkeypatch):
    from config_manager import ConfigManager
    from machine_card_root_runtime import install_machine_cards_root_path

    monkeypatch.setenv("WM_ROOT", r"C:\folder wm")
    before = ConfigManager.path_root
    install_machine_cards_root_path()
    current = ConfigManager.path_root
    fake = object.__new__(ConfigManager)
    try:
        assert current(fake, "wydruki", "karty") == r"C:\folder wm\wydruki\karty"
    finally:
        ConfigManager.path_root = before
