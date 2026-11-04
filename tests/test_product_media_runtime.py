from pathlib import Path

from PIL import Image

from planista_product_media_runtime import resolve_product_media, store_product_media


def test_store_product_photo_and_create_thumbnail(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (1200, 800), "white").save(source)
    data = tmp_path / "data"

    stored = store_product_media(data, "PR-001", "zdjecie", source)

    original = resolve_product_media(data, stored["path"])
    thumbnail = resolve_product_media(data, stored["thumbnail"])
    assert original is not None and original.is_file()
    assert thumbnail is not None and thumbnail.is_file()
    with Image.open(thumbnail) as image:
        assert image.width <= 480
        assert image.height <= 360


def test_store_technical_drawing_image(tmp_path):
    source = tmp_path / "drawing.jpg"
    Image.new("RGB", (800, 600), "white").save(source)
    stored = store_product_media(tmp_path / "data", "PR-002", "rysunek_techniczny", source)
    assert resolve_product_media(tmp_path / "data", stored["path"]).is_file()
    assert resolve_product_media(tmp_path / "data", stored["thumbnail"]).is_file()


def test_store_technical_drawing_pdf_without_thumbnail(tmp_path):
    source = tmp_path / "drawing.pdf"
    source.write_bytes(b"%PDF-1.4\n% test")
    data = tmp_path / "data"
    stored = store_product_media(data, "PR-003", "rysunek_techniczny", source)
    assert resolve_product_media(data, stored["path"]).read_bytes().startswith(b"%PDF")
    assert stored["thumbnail"] == ""


def test_missing_media_is_handled_without_error(tmp_path):
    assert resolve_product_media(tmp_path, "produkty_media/missing/photo.jpg") is None


def test_media_path_cannot_escape_data_directory(tmp_path):
    assert resolve_product_media(tmp_path, "../outside.jpg") is None


def test_replacing_media_keeps_previous_file_for_archived_versions(tmp_path):
    data = tmp_path / "data"
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (20, 20), "white").save(first)
    Image.new("RGB", (30, 30), "black").save(second)

    old = store_product_media(data, "PR-004", "zdjecie", first)
    new = store_product_media(data, "PR-004", "zdjecie", second)

    assert old["path"] != new["path"]
    assert resolve_product_media(data, old["path"]).is_file()
    assert resolve_product_media(data, new["path"]).is_file()
