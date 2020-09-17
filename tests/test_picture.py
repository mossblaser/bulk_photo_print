import pytest

import os

from bulk_photo_print.picture import Picture, FitMode

TEST_DIR = os.path.dirname(__file__)

TEST_JPEG_PORTRAIT = os.path.join(TEST_DIR, "portrait.jpg")
TEST_JPEG_LANDSCAPE = os.path.join(TEST_DIR, "landscape.jpg")
TEST_JPEG_SQUARE = os.path.join(TEST_DIR, "square.jpg")


class TestPicture:
    def test_image_size(self) -> None:
        pp = Picture.from_spec(TEST_JPEG_PORTRAIT, 1, 1)
        assert pp.image_width == 192
        assert pp.image_height == 256

        lp = Picture.from_spec(TEST_JPEG_LANDSCAPE, 1, 1)
        assert lp.image_width == 256
        assert lp.image_height == 192

    def test_width_height_crop_mode(self) -> None:
        p = Picture.from_spec(
            TEST_JPEG_PORTRAIT, 1.25, 2.5, FitMode.crop, rotate_for_best_fit=False
        )
        assert p.width == 1.25
        assert p.height == 2.5

    @pytest.mark.parametrize(
        "filename, dw, dh, ew, eh",
        [
            # Space is taller than needed
            (TEST_JPEG_PORTRAIT, 3.0, 5.0, 3.0, 4.0),
            (TEST_JPEG_LANDSCAPE, 3.0, 5.0, 3.0, 2.25),
            (TEST_JPEG_LANDSCAPE, 3.0, 3.0, 3.0, 2.25),
            (TEST_JPEG_LANDSCAPE, 3.0, 2.5, 3.0, 2.25),
            (TEST_JPEG_SQUARE, 3.0, 5.0, 3.0, 3.0),
            # Space is wider than needed
            (TEST_JPEG_PORTRAIT, 2.5, 3.0, 2.25, 3.0),
            (TEST_JPEG_PORTRAIT, 3.0, 3.0, 2.25, 3.0),
            (TEST_JPEG_PORTRAIT, 3.5, 3.0, 2.25, 3.0),
            (TEST_JPEG_LANDSCAPE, 8.0, 3.0, 4.0, 3.0),
            (TEST_JPEG_SQUARE, 5.0, 3.0, 3.0, 3.0),
            # Space is exactly right
            (TEST_JPEG_PORTRAIT, 3.0, 4.0, 3.0, 4.0),
            (TEST_JPEG_LANDSCAPE, 4.0, 3.0, 4.0, 3.0),
            (TEST_JPEG_SQUARE, 3.0, 3.0, 3.0, 3.0),
        ],
    )
    def test_width_height_scale_mode(
        self, filename: str, dw: float, dh: float, ew: float, eh: float
    ) -> None:
        p = Picture.from_spec(
            filename, dw, dh, FitMode.scale, rotate_for_best_fit=False
        )
        assert p.width == ew
        assert p.height == eh

    def test_rotate_for_best_fit(self) -> None:
        pp = Picture.from_spec(TEST_JPEG_PORTRAIT, 4, 3)
        assert pp.rotate_image
        assert pp.image_width == 256
        assert pp.image_height == 192
        assert pp.width == 4
        assert pp.height == 3

        lp = Picture.from_spec(TEST_JPEG_LANDSCAPE, 3, 4)
        assert lp.rotate_image
        assert lp.image_width == 192
        assert lp.image_height == 256
        assert lp.width == 3
        assert lp.height == 4

        sq1 = Picture.from_spec(TEST_JPEG_SQUARE, 3, 4)
        assert not sq1.rotate_image
        assert sq1.width == 3
        assert sq1.height == 4

        sq2 = Picture.from_spec(TEST_JPEG_SQUARE, 4, 3)
        assert not sq2.rotate_image
        assert sq2.width == 4
        assert sq2.height == 3

        sq3 = Picture.from_spec(TEST_JPEG_SQUARE, 3, 3)
        assert not sq3.rotate_image
        assert sq3.width == 3
        assert sq3.height == 3

    def test_pixels_per_mm(self) -> None:
        # No change
        p1 = Picture.from_spec(TEST_JPEG_LANDSCAPE, 25.6, 19.2, pixels_per_mm=None)
        assert p1.scale == 1 / 10.0
        assert p1.image_width == 256
        assert p1.image_height == 192

        # Resolution must be halved
        p2 = Picture.from_spec(TEST_JPEG_LANDSCAPE, 25.6, 19.2, pixels_per_mm=5.0)
        assert p2.scale == 1 / 5.0
        assert p2.image_width == 128
        assert p2.image_height == 96

        # Resolution is (exactly) sufficient
        p3 = Picture.from_spec(TEST_JPEG_LANDSCAPE, 25.6, 19.2, pixels_per_mm=10.0)
        assert p3.scale == 1 / 10.0
        assert p3.image_width == 256
        assert p3.image_height == 192

        # Resolution is lower than limit (no change)
        p4 = Picture.from_spec(TEST_JPEG_LANDSCAPE, 25.6, 19.2, pixels_per_mm=20.0)
        assert p4.scale == 1 / 10.0
        assert p4.image_width == 256
        assert p4.image_height == 192
