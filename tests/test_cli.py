import pytest

import os

import sys

from typing import Set, Any

from bulk_photo_print.cli import (
    parse_dimension,
    ARGUMENTS,
    parse_arguments,
    ArgumentParserError,
    main,
)

TEST_DIR = os.path.dirname(__file__)

TEST_JPEG_PORTRAIT = os.path.join(TEST_DIR, "portrait.jpg")
TEST_JPEG_LANDSCAPE = os.path.join(TEST_DIR, "landscape.jpg")
TEST_JPEG_SQUARE = os.path.join(TEST_DIR, "square.jpg")


class TestParseDimension:
    @pytest.mark.parametrize(
        "example, exp",
        [
            # Different number formats
            ("1", 1.0),
            ("1.", 1.0),
            ("123", 123.0),
            ("1.25", 1.25),
            (".25", 0.25),
            # Units
            ("1mm", 1.0),
            ("1cm", 10.0),
            ("1 m", 1000.0),
        ],
    )
    def test_valid_cases(self, example: str, exp: float) -> None:
        assert parse_dimension(example) == exp

    @pytest.mark.parametrize(
        "example",
        [
            # Empty string
            "",
            # No digits
            ".",
            # Just unit
            "mm",
            # Unknown unit
            "100 foo",
        ],
    )
    def test_invalid_cases(self, example: str) -> None:
        with pytest.raises(ValueError):
            parse_dimension(example)


def test_no_duplicate_arguments() -> None:
    names: Set[str] = set()
    for argument in ARGUMENTS.values():
        assert len(argument.argument_names) >= 1
        for name in argument.argument_names:
            assert name not in names
            names.add(name)


class TestParseArguments:
    def test_empty(self) -> None:
        args = parse_arguments([""])
        assert args.page_width == 210
        assert args.page_height == 297
        assert args.margin == 5
        assert args.pictures == []
        assert args.output_filename == "out.pdf"

    def test_page_dimensions(self) -> None:
        args = parse_arguments(["", "--page-dimensions", "100", "200"])
        assert args.page_width == 100
        assert args.page_height == 200

    def test_page_dimensions_bad_args(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--page-dimensions"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--page-dimensions", "100"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--page-dimensions", "100", "nope"])

    def test_page_dimensions_after_picture(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", TEST_JPEG_SQUARE, "--page-dimensions", "100", "200"])

    def test_margin(self) -> None:
        args = parse_arguments(["", "--margin", "12"])
        assert args.margin == 12

    def test_margin_bad_args(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--margin"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--margin", "nope"])

    def test_margin_after_picture(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", TEST_JPEG_SQUARE, "--margin", "100"])

    def test_output(self) -> None:
        args = parse_arguments(["", "--output", "foo.pdf"])
        assert args.output_filename == "foo.pdf"

    def test_output_missing(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--output"])

    def test_picture_dimensions(self) -> None:
        args = parse_arguments(
            [
                "",
                "--picture-dimensions",
                "10",
                "20",
                TEST_JPEG_SQUARE,
                "--picture-dimensions",
                "30",
                "40",
                TEST_JPEG_SQUARE,
            ]
        )

        assert len(args.pictures) == 2
        assert args.pictures[0].width == 10
        assert args.pictures[0].height == 20
        assert args.pictures[1].width == 30
        assert args.pictures[1].height == 40

    def test_picture_dimensions_bad_dimensions(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--picture-dimensions"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--picture-dimensions", "100"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--picture-dimensions", "100", "nope"])

    def test_scale_or_crop(self) -> None:
        args = parse_arguments(
            [
                "",
                "--picture-dimensions",
                "10",
                "20",
                TEST_JPEG_SQUARE,
                "--scale",
                TEST_JPEG_SQUARE,
                "--crop",
                TEST_JPEG_SQUARE,
            ]
        )

        assert len(args.pictures) == 3

        assert args.pictures[0].width == 10
        assert args.pictures[0].height == 20

        assert args.pictures[1].width == 10
        assert args.pictures[1].height == 10

        assert args.pictures[2].width == 10
        assert args.pictures[2].height == 20

    def test_alignment(self) -> None:
        args = parse_arguments(
            [
                "",
                "--picture-dimensions",
                "1",
                "2",
                TEST_JPEG_PORTRAIT,
                "--alignment",
                "0.5",
                "0.5",
                TEST_JPEG_PORTRAIT,
                "--alignment",
                "0.0",
                "0.0",
                TEST_JPEG_PORTRAIT,
            ]
        )

        assert len(args.pictures) == 3

        assert args.pictures[0].x_offset or args.pictures[0].y_offset

        assert args.pictures[0].x_offset == args.pictures[1].x_offset
        assert args.pictures[0].y_offset == args.pictures[1].y_offset

        assert args.pictures[2].x_offset == 0
        assert args.pictures[2].y_offset == 0

    def test_alignment_bad(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--alignment"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--alignment", "1"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--alignment", "1", "nope"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--alignment", "1", "2"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--alignment", "1", "-1"])

    def test_rotate_for_best_fit(self) -> None:
        args = parse_arguments(
            [
                "",
                "--scale",
                "--picture-dimensions",
                "60",
                "90",
                TEST_JPEG_LANDSCAPE,
                "--rotate-for-best-fit",
                TEST_JPEG_LANDSCAPE,
                "--no-rotate-for-best-fit",
                TEST_JPEG_LANDSCAPE,
            ]
        )

        assert len(args.pictures) == 3
        assert args.pictures[0].rotate_image
        assert args.pictures[1].rotate_image
        assert not args.pictures[2].rotate_image

    def test_dpi(self) -> None:
        args = parse_arguments(
            [
                "",
                "--picture-dimensions",
                "100",
                "100",
                "--max-dpi",
                "25.4",  # 1 dot per mm
                TEST_JPEG_SQUARE,
                "--max-dpi",
                "0",  # unlimited dpi
                TEST_JPEG_SQUARE,
            ]
        )

        assert len(args.pictures) == 2

        assert args.pictures[0].image_width == 100
        assert args.pictures[0].image_height == 100

        assert args.pictures[1].image_width == 256
        assert args.pictures[1].image_height == 256

    def test_dpi_bad(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--max-dpi"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--max-dpi", "nope"])

    def test_unknown_argument(self) -> None:
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "-?"])
        with pytest.raises(ArgumentParserError):
            parse_arguments(["", "--foo"])


class TestMain:
    def test_empty(self, tmpdir: Any, monkeypatch: Any) -> None:
        output_filename = str(tmpdir.join("out.pdf"))
        monkeypatch.setattr(sys, "argv", ["", "-o", output_filename])

        main()  # Shouldn't crash

        assert os.path.isfile(output_filename)

    def test_pictures(self, tmpdir: Any, monkeypatch: Any) -> None:
        output_filename = str(tmpdir.join("out.pdf"))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "",
                "-o",
                output_filename,
                TEST_JPEG_PORTRAIT,
                TEST_JPEG_SQUARE,
                TEST_JPEG_LANDSCAPE,
            ],
        )

        main()  # Shouldn't crash

        assert os.path.isfile(output_filename)

    def test_argument_error(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(sys, "argv", ["", "--foo"])
        with pytest.raises(SystemExit):
            main()

    def test_non_fitting_error(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "",
                "--picture-dimensions",
                "1000",
                "1000",
                TEST_JPEG_PORTRAIT,
            ],
        )
        with pytest.raises(SystemExit):
            main()
