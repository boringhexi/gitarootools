#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""png2imx.py - command-line tool to convert PNG images to IMX images"""

import argparse
import os
import sys

from gitarootools.image.imximage import PIXEL_FORMATS, read_from_png, write_imx
from gitarootools.miscutils.cmdutils import (
    argparse_exit_if_no_paths,
    glob_all,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import IMX_EXT, PIXFMT_EXAMPLE, PNG_EXT

_d = os.path.extsep


def build_argparser():
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"""Convert multiple PNG images to {IMX_EXT} image format. By default, output \
pixel format will be determined from the PNG filename \
(e.g. in{_d}{PIXFMT_EXAMPLE}{PNG_EXT} outputs a {PIXFMT_EXAMPLE} IMX image)"""
    )
    parser.add_argument(
        dest="input_pngfiles",
        metavar="INPUT_PNGFILE",
        nargs="+",
        help=f"path to one or more {PNG_EXT} image files",
    )
    parser.add_argument(
        "-a",
        "--auto-pixfmt",
        dest="auto_pixfmt",
        action="store_true",
        help=(
            "always automatically choose a pixel format based on image contents, "
            "even if the filename contains one"
        ),
    )
    parser.add_argument(
        "-s",
        "--strip-pixfmt-name",
        dest="strip_pixfmt_name",
        action="store_true",
        help=(
            "strip the pixel format from the end of the output IMX filename, "
            f"(e.g. file{_d}{PIXFMT_EXAMPLE}{PNG_EXT} -> file{IMX_EXT})"
        ),
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTDIR",
        default="",  # current working directory
        dest="directory",
        help="directory to which converted files will be written (uses the current "
        "working directory if not specified)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="list files as they are converted",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Pixel Formats:
  To use a pixel format, put it at the end of the input filename, e.g. \
file{_d}{PIXFMT_EXAMPLE}{PNG_EXT}

  Available pixel formats are:
    rgba32: full RGBA color with transparency
    rgb24: full RGB color, no transparency
    i8: indexed, 256-color RGBA palette
    i4: indexed, 16-color RGBA palette

    Notes:
      - If the input filename doesn't end with a pixel format, it will be \
chosen automatically. Pass -a to always do this regardless of filename.
      - When saving to an indexed format, colors will be automatically reduced to fit \
into the palette.
      - For i4 pixel format, the image's width must be an even number.

Examples:
  Example 1: Convert a PNG to {IMX_EXT}
     {parser.prog} file{_d}{PIXFMT_EXAMPLE}{PNG_EXT}

  Example 2: Convert multiple PNGS to {IMX_EXT}
     {parser.prog} file{_d}{PIXFMT_EXAMPLE}{PNG_EXT} file2{_d}{PIXFMT_EXAMPLE}{PNG_EXT}

  Example 3: Convert multiple PNGS with a wildcard, list files as they are converted
     {parser.prog} -v *{PNG_EXT}

  Example 4: Output all converted {IMX_EXT} images to outdir{s}
     {parser.prog} -d outdir *{PNG_EXT}

Notes:
  Other input image formats may work, but only PNG is guaranteed.
"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""

    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    # get all input paths, or exit with an error if there aren't any
    all_inpaths = glob_all(parsed_args.input_pngfiles)
    argparse_exit_if_no_paths(all_inpaths, progname=parser.prog)

    # create outdir if it doesn't exist (now that we know we have at least 1 input file)
    outdir = parsed_args.directory
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    # process all input paths
    for inpath in all_inpaths:

        # try to get pixel format from filename, e.g. filename.<pixfmt>.png
        pixfmt = os.path.splitext(os.path.splitext(inpath)[0])[1][1:]
        do_strip_pixfmt = parsed_args.strip_pixfmt_name and pixfmt in PIXEL_FORMATS
        if parsed_args.auto_pixfmt or pixfmt not in PIXEL_FORMATS:
            pixfmt = None

        # create output filename/path
        outname_noext = os.path.splitext(os.path.basename(inpath))[0]
        if do_strip_pixfmt:
            outname_noext = os.path.splitext(outname_noext)[0]
        outname = f"{outname_noext}{IMX_EXT}"
        outpath = os.path.join(outdir, outname)

        if parsed_args.verbose:
            print(f"converting {inpath!r} -> {outpath!r}")
        imximage = read_from_png(inpath, pixfmt=pixfmt)
        write_imx(imximage, outpath)


if __name__ == "__main__":
    main()
