import os
import gui_narzedzia


def test_is_allowed_file(tmp_path):
    good = tmp_path / "ok.png"
    good.write_bytes(b"x")
    assert gui_narzedzia._is_allowed_file(str(good))

    bad_ext = tmp_path / "bad.txt"
    bad_ext.write_bytes(b"x")
    assert not gui_narzedzia._is_allowed_file(str(bad_ext))

    big = tmp_path / "big.png"
    big.write_bytes(b"x" * (gui_narzedzia.MAX_FILE_SIZE + 1))
    assert not gui_narzedzia._is_allowed_file(str(big))


def test_remove_task_deletes_files(tmp_path):
    media = tmp_path / "m.png"
    thumb = tmp_path / "t.jpg"
    media.write_bytes(b"1")
    thumb.write_bytes(b"1")
    tasks = [{"tytul": "a", "done": False, "media": str(media), "miniatura": str(thumb)}]
    gui_narzedzia._remove_task(tasks, 0)
    assert tasks == []
    assert not media.exists()
    assert not thumb.exists()
