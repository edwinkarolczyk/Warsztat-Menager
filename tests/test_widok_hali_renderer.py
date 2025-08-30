import pytest

from widok_hali.renderer import Image, checkerboard, render


@pytest.mark.skipif(Image is None, reason="Pillow is not available")
def test_render_accepts_image_background():
    bg = checkerboard(64, 64, 8)
    config = {"background": bg, "sprites": {}}
    assert render(config) is bg
