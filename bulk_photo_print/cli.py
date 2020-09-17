"""
A simple CLI interface to this software.
"""

import sys

import os

import re

from dataclasses import dataclass

from typing import List, NamedTuple, Optional, Mapping

from bulk_photo_print.picture import Picture, FitMode
from bulk_photo_print.packing import pack, PicturesDoNotFitError
from bulk_photo_print.render import render

import shutil

import textwrap


UNITS = {
    "": 1.0,
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
    '"': 25.4,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    "'": 304.8,
    "ft": 304.8,
    "foot": 304.8,
    "feet": 304.8,
}
"""
Conversions from common units to millimeters.
"""

DIMENSION_REGEX = re.compile(
    r"(\d+(?:[.]\d*)?|[.]\d+)\s*({})".format("|".join(re.escape(u) for u in UNITS)),
    re.IGNORECASE | re.ASCII,
)


def parse_dimension(dimension: str) -> float:
    """Parse a dimension specification string into millimeters."""
    match = DIMENSION_REGEX.fullmatch(dimension)
    if match is None:
        raise ValueError(dimension)
    else:
        number, unit = match.groups()
        return float(number) * UNITS[unit.lower()]


@dataclass
class ParsedArguments:
    pictures: List[Picture]
    """The pictures to print (with dimensions in mm)."""

    page_width: float = 210.0
    page_height: float = 297.0
    """The page size to print onto, in mm."""

    margin: float = 5.0
    """The margin to leave around the page edge, in mm."""

    output_filename: str = "out.pdf"
    """The filename to write the generated PDF to."""


class ArgumentParserError(Exception):
    """Parse error during argument parsing."""


class ShowHelp(Exception):
    """
    Thrown when the arguments indicate that the program should display a help
    message and then exit. See :py:func:`render_help`.
    """


class Argument(NamedTuple):
    argument_names: List[str]
    metavariable: Optional[str]
    help: str


ARGUMENTS: Mapping[str, Argument] = {
    "help": Argument(
        ["--help", "-h"],
        None,
        "Show help information and exit.",
    ),
    "page_dimensions": Argument(
        ["--page-dimensions", "-p"],
        "WIDTH HEIGHT",
        "The page dimensions. Defaults to A4 (210mm 297mm).",
    ),
    "margin": Argument(
        ["--margin", "-m"],
        "SIZE",
        "The margin size between the page edge and all pictures. Defaults to 5mm.",
    ),
    "output": Argument(
        ["--output", "-o"],
        "FILENAME",
        "The output filename. Defaults to out.pdf.",
    ),
    "picture_dimensions": Argument(
        ["--picture-dimensions", "-d"],
        "WIDTH HEIGHT",
        """
            The picture dimensions (defaults to 3\" 4\"). May be used multiple
            times, applying only to pictures following its use.
        """,
    ),
    "crop": Argument(
        ["--crop", "-c"],
        None,
        """
            Scale and crop pictures to fill the desired picture dimensions
            exactly. This is the default behaviour. See also: --scale. Applies
            only to pictures following this argument.
        """,
    ),
    "scale": Argument(
        ["--scale", "-s"],
        None,
        """
            Scale pictures to the largest size which fits entirely within the
            desired picture dimensions while maintaining the original aspect
            ratio.  See also: --crop. Applies only to pictures following this
            argument.
        """,
    ),
    "alignment": Argument(
        ["--alignment", "-a"],
        "X-ALIGNMENT Y-ALIGNMENT",
        """
            When '--crop' mode is used, controls which part of the picture will
            be cropped. Two numbers in the range 0.0 to 1.0 must be given
            specifying the alignment of the picture with respect to any
            cropping. For example the default is '0.5 0.5' meaning crop to the
            center of the image. Applies only to pictures following this
            argument.
        """,
    ),
    "rotate_for_best_fit": Argument(
        ["--rotate-for-best-fit", "-r"],
        None,
        """
            Allow pictures to be rotated to best fit the picture dimensions
            given, for example rotating landscape pictures to fit better when
            the picture dimension given are portrait. This is the default
            behaviour. See also: --no-rotate-for-best-fit. Applies only to
            pictures following this argument.
        """,
    ),
    "no_rotate_for_best_fit": Argument(
        ["--no-rotate-for-best-fit", "-R"],
        None,
        """
            Do not rotate pictures to better fit the specified picture size.
            See also: --rotate-for-best-fit. Applies only to pictures following
            this argument.
        """,
    ),
    "dpi": Argument(
        ["--max-dpi", "-D"],
        "DPI",
        """
            Set the maximum resolution for the images in the output PDF in Dots
            Per Inch (DPI). Defaults to 300 DPI. Set to 0 to use original
            resolution.
        """,
    ),
}
"""
All supported arguments along with metavariables for the argument and
documentation strings.
"""


def parse_arguments(args: List[str]) -> ParsedArguments:
    """
    Parse the CLI arguments. Note that we don't use the excellent
    :py:mod:`argparse` module because it does not support stateful arguments
    which offer the most concise format for this application.
    """
    # Page dimensions and margin. Defaults to A4 with 5mm margins. Must be set
    # before any pictures are specified.
    page_width: float = parse_dimension("210mm")
    page_height: float = parse_dimension("297mm")
    margin: float = parse_dimension("5mm")

    output_filename: str = "out.pdf"

    # Picture dimensions. Defaults to cropping to fit a 3x4" standard size. Can
    # be altered as arguments are parsed.
    desired_width: float = parse_dimension("3 inches")
    desired_height: float = parse_dimension("4 inches")
    fit_mode: FitMode = FitMode.crop
    x_alignment: float = 0.5
    y_alignment: float = 0.5
    rotate_for_best_fit: bool = True
    pixels_per_mm: Optional[float] = 300 / parse_dimension("1 inch")

    pictures: List[Picture] = []

    args = args[1:]  # Strip program name (and make a copy for mutation)
    while args:
        argument = args.pop(0)

        if argument in ARGUMENTS["help"].argument_names:
            raise ShowHelp()
        elif argument in ARGUMENTS["page_dimensions"].argument_names:
            if len(pictures) != 0:
                raise ArgumentParserError(
                    "{argument} must appear before picture filenames"
                )
            try:
                page_width = parse_dimension(args.pop(0))
                page_height = parse_dimension(args.pop(0))
            except IndexError:
                raise ArgumentParserError(f"{argument} expects a WIDTH and HEIGHT")
            except ValueError:
                raise ArgumentParserError(f"invalid dimension passed to {argument}")
        elif argument in ARGUMENTS["margin"].argument_names:
            if len(pictures) != 0:
                raise ArgumentParserError(
                    "{argument} must appear before picture filenames"
                )
            try:
                margin = parse_dimension(args.pop(0))
            except IndexError:
                raise ArgumentParserError(f"{argument} expects a SIZE")
            except ValueError:
                raise ArgumentParserError(f"invalid dimension passed to {argument}")
        elif argument in ARGUMENTS["output"].argument_names:
            try:
                output_filename = args.pop(0)
            except IndexError:
                raise ArgumentParserError(f"{argument} expects a FILENAME")
        elif argument in ARGUMENTS["picture_dimensions"].argument_names:
            try:
                desired_width = parse_dimension(args.pop(0))
                desired_height = parse_dimension(args.pop(0))
            except IndexError:
                raise ArgumentParserError(f"{argument} expects a WIDTH and HEIGHT")
            except ValueError:
                raise ArgumentParserError(f"invalid dimension passed to {argument}")
        elif argument in ARGUMENTS["crop"].argument_names:
            fit_mode = FitMode.crop
        elif argument in ARGUMENTS["scale"].argument_names:
            fit_mode = FitMode.scale
        elif argument in ARGUMENTS["alignment"].argument_names:
            try:
                x_alignment = float(args.pop(0))
                y_alignment = float(args.pop(0))
                if not (0.0 <= x_alignment <= 1.0 and 0.0 <= y_alignment <= 1.0):
                    raise ValueError("Alignment not in range 0.0 to 1.0")
            except IndexError:
                raise ArgumentParserError(
                    f"{argument} expects an X-ALIGNMENT and Y-ALIGNMENT"
                )
            except ValueError:
                raise ArgumentParserError(f"invalid alignment passed to {argument}")
        elif argument in ARGUMENTS["rotate_for_best_fit"].argument_names:
            rotate_for_best_fit = True
        elif argument in ARGUMENTS["no_rotate_for_best_fit"].argument_names:
            rotate_for_best_fit = False
        elif argument in ARGUMENTS["dpi"].argument_names:
            try:
                dpi = float(args.pop(0))
            except IndexError:
                raise ArgumentParserError(f"{argument} expects a DPI")
            except ValueError:
                raise ArgumentParserError(f"invalid DPI passed to {argument}")
            if dpi <= 0:
                pixels_per_mm = None
            else:
                pixels_per_mm = dpi / parse_dimension("1 inch")
        elif argument.startswith("-"):
            raise ArgumentParserError(f"unknown argument {argument}")
        else:
            filename = argument

            # If allowing rotations, rotate the desired width/height to better
            # match this paper's orientation. In general this results in
            # superiour packing performance for the picture packing heuristic
            # with smaller pictures.
            page_aspect = page_height / page_width
            desired_aspect = desired_height / desired_width
            if (
                rotate_for_best_fit
                and page_aspect != 1.0
                and desired_aspect != 1.0
                and (page_aspect > 1.0) != (desired_aspect > 1.0)
                # Don't rotate if already very nearly the size of the page
                and desired_width < page_width / 2
                and desired_height < page_height / 2
            ):
                this_desired_width = desired_height
                this_desired_height = desired_width
            else:
                this_desired_width = desired_width
                this_desired_height = desired_height

            pictures.append(
                Picture.from_spec(
                    filename=filename,
                    desired_width=this_desired_width,
                    desired_height=this_desired_height,
                    fit_mode=fit_mode,
                    x_alignment=x_alignment,
                    y_alignment=y_alignment,
                    rotate_for_best_fit=rotate_for_best_fit,
                    pixels_per_mm=pixels_per_mm,
                )
            )

    return ParsedArguments(
        pictures=pictures,
        page_width=page_width,
        page_height=page_height,
        margin=margin,
        output_filename=output_filename,
    )


def wrap(text: str, indent: str = "") -> str:
    """
    Indent and line-wrap a string to fit in the current terminal width.
    """
    width = shutil.get_terminal_size((80, 20)).columns
    return textwrap.indent(textwrap.fill(text, width - len(indent)), indent)


def dedent_and_wrap(text: str, indent: str = "") -> str:
    return wrap(textwrap.dedent(text), indent)


def render_usage_summary(program_name: str) -> str:
    usage = f"usage: {program_name} "
    arguments = " ".join(
        f"[{arg.argument_names[0]}]"
        if arg.metavariable is None
        else f"[{arg.argument_names[0]} {arg.metavariable}]"
        for arg in ARGUMENTS.values()
    )
    indent = " " * len(usage)
    return (
        usage + wrap(arguments, indent).lstrip() + "\n" + wrap("[FILENAME ...]", indent)
    )


def render_argument(argument: str, description: str, indent: int = 24) -> str:
    argument = "  " + argument

    if len(argument) >= indent:
        return argument + "\n" + dedent_and_wrap(description, " " * indent)
    else:
        return (
            argument.ljust(indent) + dedent_and_wrap(description, " " * indent).lstrip()
        )


def render_help(program_name: str) -> str:
    out = ""

    out += render_usage_summary(program_name)
    out += "\n\n"

    out += dedent_and_wrap(
        """
            Automatically arange multiple, variously-sized photographs,
            trying to fit as many as possible per page.
        """
    )
    out += "\n\n"

    out += "positional arguments:\n"
    out += render_argument("FILENAME", "The filenames of the files to be printed.")
    out += "\n\n"

    out += "optional arguments:\n"
    for argument in ARGUMENTS.values():
        argument_string = ", ".join(
            f"{name}"
            if argument.metavariable is None
            else f"{name} {argument.metavariable}"
            for name in argument.argument_names
        )
        out += render_argument(argument_string, argument.help)
        out += "\n"

    return out.rstrip()


def main() -> None:
    program_name = os.path.basename(sys.argv[0])

    # Parse arguments
    try:
        args = parse_arguments(sys.argv)
    except ShowHelp:
        print(render_help(program_name))
        return
    except ArgumentParserError as exc:
        sys.stderr.write(render_usage_summary(program_name) + "\n")
        sys.stderr.write(f"error: {wrap(str(exc))}\n")
        sys.exit(1)

    # Pack pictures
    try:
        picture_locations = pack(
            args.pictures,
            args.page_width - args.margin * 2,
            args.page_height - args.margin * 2,
        )
    except PicturesDoNotFitError:
        sys.stderr.write("error: picture too large for page\n")
        sys.exit(2)

    # Render output
    render(
        args.output_filename,
        args.page_width,
        args.page_height,
        args.margin,
        picture_locations,
    )

    return


if __name__ == "__main__":
    main()
