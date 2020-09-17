import math

from typing import List

from dataclasses import dataclass

from bulk_photo_print.packing import PictureLocation
from bulk_photo_print.picture import Picture

import cairo


def mm_to_pt(mm: float) -> float:
    return mm * 2.8346457


def render_picture(ctx: cairo.Context, picture: Picture) -> None:
    """
    Render a picture at (0, 0) onto the supplied context (which should use mm
    units).
    """
    ctx.save()

    # Load the picture
    image_surface = cairo.ImageSurface.create_for_data(
        picture.get_image_bytes(),
        cairo.FORMAT_ARGB32,
        picture.image_width,
        picture.image_height,
    )

    # Scale and translate the picture according to the scale/crop mode in use.
    #
    # NB: Pattern matrix maps from page space to pixel space, hence the
    # apparently inverted transformation described here.
    ctx.set_source_surface(image_surface)
    pattern = ctx.get_source()
    m = pattern.get_matrix()
    m.scale(1 / picture.scale, 1 / picture.scale)
    m.translate(-picture.x_offset, -picture.y_offset)
    pattern.set_matrix(m)

    # Draw the picture (clipped)
    ctx.rectangle(0, 0, picture.width, picture.height)
    ctx.fill()

    ctx.restore()


def render(
    pdf_filename: str,
    page_width: float,
    page_height: float,
    page_margin: float,
    picture_locations: List[List[PictureLocation]],
) -> None:
    """
    Render a packed set of pictures into a PDF.

    Picture locations and sizes should be given in millimeters with (0, 0)
    being the coordinate of the top-left of the page within the page margin.
    """

    with cairo.PDFSurface(
        pdf_filename, mm_to_pt(page_width), mm_to_pt(page_height)
    ) as surface:
        for page_number, page in enumerate(picture_locations):
            if page_number != 0:
                surface.show_page()

            for picture_location in page:
                ctx = cairo.Context(surface)
                ctx.scale(mm_to_pt(1), mm_to_pt(1))  # Use mm as unit
                ctx.translate(page_margin, page_margin)

                # Translate and rotate according to packing outcome
                ctx.translate(picture_location.x, picture_location.y)
                if picture_location.rotated:
                    ctx.rotate(math.pi / 2.0)
                    ctx.translate(0, -picture_location.picture.height)

                render_picture(ctx, picture_location.picture)
