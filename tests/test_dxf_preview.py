import os
import pytest
from gui_narzedzia import _generate_dxf_preview


def test_dxf_preview_resized(tmp_path):
    try:
        import ezdxf
        from PIL import Image
    except Exception:
        pytest.skip("ezdxf or Pillow not installed")

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 10))
    dxf_path = tmp_path / "sample.dxf"
    doc.saveas(dxf_path)

    png_path = _generate_dxf_preview(str(dxf_path))
    assert png_path is not None
    assert os.path.exists(png_path)

    with Image.open(png_path) as img:
        width, height = img.size

    assert width <= 600 and height <= 800
