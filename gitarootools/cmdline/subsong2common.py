# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""subsong2common.py - common stuff used by the subsong2xxx scripts"""

import argparse
import os

from gitarootools.audio.subsong import read_subsong, write_subsong
from gitarootools.miscutils.cmdutils import (
    argparse_exit_if_no_paths,
    glob_all,
    make_check_input_path,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import SUBSONG_FORMATS, subsong_replaceext


def build_argparser_for_outformat(subsongtype):
    """build a command line parser for a gm-subsong2foo script

    subsongtype: a key from extutils.SUBSONG_FORMATS, e.g. "wav" This determines:
      - output file extension (same as subsongtype)
      - allowed input file extensions (all SUBSONG_FORMATS except subsongtype)
      - the help text (mentions of input and output file extensions)
    """
    # determine which input and output formats to support
    # (e.g. no point in converting a subsong to its own type)
    supported_input_extensions = [
        SUBSONG_FORMATS[k] for k in SUBSONG_FORMATS if k is not subsongtype
    ]
    output_extension = SUBSONG_FORMATS[subsongtype]

    # create the argument parser
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Convert multiple subsongs to {output_extension} subsong format"
    )
    parser.add_argument(
        dest="input_subsongfiles",
        metavar="INPUT_SUBSONGFILE",
        nargs="+",
        help="path to one or more subsong files (supported input formats/"
        f"extensions are: {', '.join(supported_input_extensions)})",
        type=make_check_input_path(*supported_input_extensions),
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
    inext, inext2 = supported_input_extensions[0], supported_input_extensions[-1]
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Convert a single subsong to {output_extension}
     {parser.prog} file{inext}

  Example 2: Convert multiple subsongs to {output_extension}
     {parser.prog} file{inext} file2{inext2}

  Example 3: Convert multiple subsongs with a wildcard, list files as they are converted
     {parser.prog} -v *{inext}

  Example 4: Output all converted subsongs to outdir{s}
     {parser.prog} -d outdir *{inext}
"""
    )
    return parser


def run_script(subsongtype, args):
    """run a subsong2xxx script with args (e.g. "wav" runs subsong2wav)

    subsongtype: a key from extutils.SUBSONG_FORMATS, e.g. "wav". Passing "wav" will run
      subsong2wav, and so on.
    args: sequence of command line argument strings, such as from sys.argv[1:]
    """
    parser = build_argparser_for_outformat(subsongtype)
    parsed_args = parser.parse_args(args)

    # get all input paths, or exit with an error if there aren't any
    all_inpaths = glob_all(parsed_args.input_subsongfiles)
    argparse_exit_if_no_paths(all_inpaths, progname=parser.prog)

    # create outdir if it doesn't exist (now that we know we have at least 1 input file)
    outdir = parsed_args.directory
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    # process all input paths
    for inpath in all_inpaths:
        outpath = subsong_replaceext(inpath, subsongtype)
        outpath = os.path.join(outdir, os.path.basename(outpath))
        if parsed_args.verbose:
            print(f"converting {inpath!r} -> {outpath!r}")
        subsong = read_subsong(inpath)
        write_subsong(subsong, outpath)
