from controller import Controller, Item


def test_drag_snaps_to_grid():
    controller = Controller(drag_snap_px=10)
    controller.items["a"] = Item(0, 0)
    controller.set_mode("move")
    controller.on_click("a")
    controller.on_drag(12, 17)
    assert controller.items["a"] == Item(10, 20)
    controller.on_drop()
    assert controller._drag_id is None
