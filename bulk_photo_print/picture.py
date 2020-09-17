from typing import cast, Tuple, Optional

from enum import Enum, auto

from dataclasses import dataclass, field

from PIL import Image  # type: ignore


class FitMode(Enum):
    scale = auto()
    """
    Scale the picture down to fit within the desired width and height, not
    necessarily completely filling that area.
    """

    crop = auto()
    """
    Scale and crop the picture down such that it fully fills the desired width
    and height.
    """


@dataclass
class Picture:
    filename: str

    rotate_image: bool
    """If True, the image must be rotated degrees after loading."""

    image_width: int
    image_height: int
    """
    Underlying image dimensions, in pixels (after rotation according to
    rotate_image).

    If different to the loaded and rotated image size, the image
    should be resampled to this size.
    """

    width: float
    height: float
    """
    The width and height of the visible area of this picture.
    """

    scale: float
    """
    Scaling factor which converts from pixels to mm at the desired size.
    """

    x_offset: float
    y_offset: float
    """
    The translation to apply after scaling but before cropping to the rectangle
    (0, 0, width, height)
    """

    @classmethod
    def from_spec(
        cls,
        filename: str,
        desired_width: float,
        desired_height: float,
        fit_mode: FitMode = FitMode.crop,
        x_alignment: float = 0.5,
        y_alignment: float = 0.5,
        rotate_for_best_fit: bool = True,
        pixels_per_mm: Optional[float] = None,
    ) -> "Picture":
        """
        Create a :py:class:`Picture`.

        When ``fit_mode`` is 'scale', the picture will be scaled as large as
        possible while not overflowing the specified size, producing a smaller
        picture in one dimension if necessary.

        When ``fit_mode`` is 'crop', the picture will be scaled to fill the
        desired space and excess will be cropped. ``x_alignment`` and
        ``y_alignment`` specify the alignment of the picture prior to cropping.
        The default (0.5, 0.5) results in a crop of the center of the picture.
        (0, 0) would result in a crop of the top or left edge (depending on the
        aspect ratio of the picture and desired size).

        When ``rotate_for_best_fit`` is used, the desired width and height may
        be swapped to better match the aspect ratio of the picture.

        The ``pixels_per_mm`` argument may be used to indicate that the image
        must be rescaled to the specified resolution. If None, no rescaling
        should occur.
        """
        im = Image.open(filename)
        image_width, image_height = cast(Tuple[int, int], im.size)
        image_aspect = image_height / image_width
        rotate_image = False

        if rotate_for_best_fit:
            desired_aspect = desired_height / desired_width
            if (
                image_aspect != 1.0
                and desired_aspect != 1.0
                and (desired_aspect > 1.0) != (image_aspect > 1.0)
            ):
                image_width, image_height = image_height, image_width
                x_alignment, y_alignment = y_alignment, x_alignment
                image_aspect = 1 / image_aspect
                rotate_image = True

        if fit_mode == FitMode.crop:
            width = desired_width
            height = desired_height

            scale_to_fit_width = width / image_width
            scale_to_fit_height = height / image_height
            scale = max(scale_to_fit_width, scale_to_fit_height)

            scaled_width = image_width * scale
            scaled_height = image_height * scale
            x_offset = -((scaled_width - width) * x_alignment)
            y_offset = -((scaled_height - height) * y_alignment)
        elif fit_mode == FitMode.scale:
            if desired_width * image_aspect <= desired_height:
                width = desired_width
                height = desired_width * image_aspect
            else:
                width = desired_height / image_aspect
                height = desired_height
            scale = width / image_width
            x_offset = 0
            y_offset = 0
        else:
            raise NotImplementedError(fit_mode)

        if pixels_per_mm is not None:
            if pixels_per_mm < (1 / scale):
                rescale = pixels_per_mm / (1 / scale)
                image_width = int(image_width * rescale)
                image_height = int(image_height * rescale)
                scale = 1 / pixels_per_mm

        return cls(
            filename=filename,
            rotate_image=rotate_image,
            image_width=image_width,
            image_height=image_height,
            width=width,
            height=height,
            scale=scale,
            x_offset=x_offset,
            y_offset=y_offset,
        )

    def get_image_bytes(self) -> memoryview:
        """
        Return a mutable memoryview of an 8bit BGRA image, decoded and rotated
        (as required) containing this picture.
        """
        im = Image.open(self.filename)

        # Rotate if necessary
        if self.rotate_image:
            im = im.transpose(Image.ROTATE_270)

        # Resize if necessary
        if cast(Tuple[int, int], im.size) != (self.image_width, self.image_height):
            im = im.resize(
                (self.image_width, self.image_height),
                Image.BICUBIC,
            )

        # Convert into RGBA
        if "A" not in im.getbands():
            im.putalpha(256)
        return memoryview(bytearray(im.tobytes("raw", "BGRa")))
