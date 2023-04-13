#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""gmo2animnames.py - command-line tool to extract animation names from .gmo models"""

import argparse
import os
import sys

from gitarootools.other.gmomodel import animnames_from_gmo, write_animnames
from gitarootools.miscutils.cmdutils import (
    argparse_exit_if_no_paths,
    glob_all,
    make_check_input_path,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import replaceext

_d = os.path.extsep


def build_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        "Extract animation names from .gmo model and save to text file"
    )
    parser.add_argument(
        dest="input_gmofiles",
        metavar="INPUT_GMOFILE",
        nargs="+",
        help=f"path to one or more .gmo image files",
        type=make_check_input_path(".gmo"),
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTDIR",
        default="",  # current working directory
        dest="directory",
        help="directory to which text files will be written (uses the current "
        "working directory if not specified)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="list files as they are processed",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Extract animation names from a .gmo file
     {parser.prog} model.gmo

  Example 2: Extract animation names from multiple .gmo files
     {parser.prog} model1.gmo model2.gmo

  Example 3: Extract from mutiple .gmo models using a wildcard, list files as they are \
processed
     {parser.prog} -v *.gmo

  Example 4: Output each text files to outdir{s}
     {parser.prog} -d outdir *.gmo
"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""

    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    # get all input paths, or exit with an error if there aren't any
    all_inpaths = glob_all(parsed_args.input_gmofiles)
    argparse_exit_if_no_paths(all_inpaths, progname=parser.prog)

    # create outdir if it doesn't exist (now that we know we have at least 1 input file)
    outdir = parsed_args.directory
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    # process all input paths
    for inpath in all_inpaths:
        # print first part of the verbose message
        if parsed_args.verbose:
            print(f"processing {inpath!r}")

        with open(inpath, "rb") as gmofile:
            outname = replaceext(os.path.basename(inpath), ".animnames")
            outpath = os.path.join(outdir, outname)
            animnames = animnames_from_gmo(gmofile)
        write_animnames(animnames, outpath)


if __name__ == "__main__":
    main()
