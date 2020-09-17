from typing import NamedTuple, List, cast

from decimal import Decimal

from dataclasses import dataclass

import rectpack  # type: ignore

from bulk_photo_print.picture import Picture


def to_decimal(number: float) -> Decimal:
    """
    A wrapper around :py:func:`rectpack.float2dec` with a fixed number of
    digits.
    """
    return cast(Decimal, rectpack.float2dec(number, 3))


class PictureLocation(NamedTuple):
    picture: Picture
    x: float
    y: float
    width: float
    height: float
    rotated: bool


class PicturesDoNotFitError(ValueError):
    """
    Thrown by :py:func:`pack` when some pictures did not fit onto the provided
    page size.
    """


def pack(
    pictures: List[Picture], page_width: float, page_height: float
) -> List[List[PictureLocation]]:
    """
    Pack a series of pictures into pages of the specified size. Returns a
    series of lists, one per page, containing :py:class:`PictureLocation`
    objects for each picture placed on that page.
    """
    packer = rectpack.newPacker(
        # Offline packing mode
        mode=rectpack.PackingMode.Offline,
        # Try each bin in turn, most promising first
        bin_algo=rectpack.PackingBin.Global,
        # Use the guillotine algorithm with Best-Area-First ('Baf'; meaning picking
        # the smallest rectangle which can fit the picture) and Minimum-Area-Split
        # ('Minas'; attempt to split free space to make the largest rectangle
        # possible).
        pack_algo=rectpack.GuillotineBafMinas,
        # Pack starting with the largest pictures first
        sort_algo=rectpack.SORT_AREA,
        # Allow pictures to be rotated.
        rotation=True,
    )

    packer.add_bin(
        width=to_decimal(page_width),
        height=to_decimal(page_height),
        # Use as many pages as necessary
        count=float("inf"),
    )

    for picture in pictures:
        packer.add_rect(
            to_decimal(picture.width),
            to_decimal(picture.height),
            picture,
        )

    packer.pack()

    out = [
        [
            PictureLocation(
                picture,
                float(x),
                float(y),
                float(width),
                float(height),
                width != to_decimal(picture.width),
            )
            for x, y, width, height, picture in page.rect_list()
        ]
        for page in packer
    ]

    # Check for missing pictures
    missing_pictures = list(pictures)
    for page in out:
        for picture_location in page:
            missing_pictures.remove(picture_location.picture)

    if missing_pictures:
        raise PicturesDoNotFitError(missing_pictures)

    return out
