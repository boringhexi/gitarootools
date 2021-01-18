#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""imx2png.py - command-line tool to convert IMX images to PNG images"""

import argparse
import os
import sys

from gitarootools.image.imximage import fast_imx_pixfmt, read_imx, write_to_png
from gitarootools.miscutils.cmdutils import (
    argparse_exit_if_no_paths,
    glob_all,
    make_check_input_path,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import IMX_EXT, PIXFMT_EXAMPLE, PNG_EXT, replaceext

_d = os.path.extsep


def build_argparser():
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"""\
Convert multiple {IMX_EXT} images to PNG image format. Output filenames will \
contain the original IMX pixel format (e.g. out{_d}{PIXFMT_EXAMPLE}{PNG_EXT})"""
    )
    parser.add_argument(
        dest="input_imxfiles",
        metavar="INPUT_IMXFILE",
        nargs="+",
        help=f"path to one or more {IMX_EXT} image files",
        type=make_check_input_path(IMX_EXT),
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
Examples:
  Example 1: Convert a file to PNG
     {parser.prog} file{IMX_EXT}

  Example 2: Convert multiple files to PNG
     {parser.prog} file{IMX_EXT} file2{IMX_EXT}

  Example 3: Convert multiple files with a wildcard, list files as they are converted
     {parser.prog} -v *{IMX_EXT}

  Example 4: Output all converted PNGs to outdir{s}
     {parser.prog} -d outdir *{IMX_EXT}
"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""

    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    # get all input paths, or exit with an error if there aren't any
    all_inpaths = glob_all(parsed_args.input_imxfiles)
    argparse_exit_if_no_paths(all_inpaths, progname=parser.prog)

    # create outdir if it doesn't exist (now that we know we have at least 1 input file)
    outdir = parsed_args.directory
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    # process all input paths
    for inpath in all_inpaths:
        # print first part of the verbose message
        if parsed_args.verbose:
            print(f"converting {inpath!r} -> ", end="")

        with open(inpath, "rb") as imxfile:
            pixfmt = fast_imx_pixfmt(imxfile)
            newext = f"{_d}{pixfmt}{PNG_EXT}"
            outname = replaceext(os.path.basename(inpath), newext)
            outpath = os.path.join(outdir, outname)
            # print rest of the verbose message, now that we know outpath
            if parsed_args.verbose:
                print(f"{outpath!r}")

            imximage = read_imx(imxfile)

        write_to_png(imximage, outpath)


if __name__ == "__main__":
    main()
