#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""xgmpack.py - command-line tool to pack XGM TOML+contents into XGM container files

Can take a specially written TOML file + XGM contents and pack them into an
XGM container file.
"""

import argparse
import os
import sys

from gitarootools.archive.xgmcontainer import write_xgm
from gitarootools.archive.xgmtoml import read_toml
from gitarootools.miscutils.cmdutils import (
    argparse_exit_if_no_paths,
    glob_all,
    glob_all_dirs_to_wildcards,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import (
    XGM_EXT,
    XGMTOML_EXT,
    XGMTOML_EXT_GLOB,
    replaceext,
)


def build_argparser():
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Pack {XGMTOML_EXT} files and their contents into {XGM_EXT} " "container files"
    )
    parser.add_argument(
        metavar="INPUT_PATH",
        nargs="+",
        dest="input_paths",
        help=f"one or more input paths. Each can be a {XGMTOML_EXT} file or a "
        f"directory containing at least one {XGMTOML_EXT} file. Directories without a "
        f"{XGMTOML_EXT} file will be skipped",
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTDIR",
        default="",  # current working directory
        dest="directory",
        help=f"directory to which each {XGM_EXT} file will be written "
        "(uses the current working directory if not specified)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help=f"list {XGM_EXT} files and their contents as they are packed",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Pack a single {XGMTOML_EXT} file
      {parser.prog} file{XGMTOML_EXT}

  Example 2: Pack any {XGMTOML_EXT} files in the current directory
      {parser.prog} {os.curdir}

  Example 3: Pack all {XGMTOML_EXT} files in the chosen directories, list files as \
they are packed
      {parser.prog} -v file{s} file2{s}

  Example 4: Use a wildcard to search multiple directories for {XGMTOML_EXT} files and \
pack them
      {parser.prog} STAGE*{s}

  Example 5: Write packed {XGM_EXT} files to a different directory
      {parser.prog} -d outdir file{XGMTOML_EXT}"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""

    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    # get all input paths, convert all dirs to *.XGM.toml paths if they contain any
    all_inpaths = glob_all(parsed_args.input_paths)
    all_inpaths_toml = glob_all_dirs_to_wildcards(all_inpaths, XGMTOML_EXT_GLOB)

    # or exit with an error if there aren't any matching paths
    errormessage = (
        f"error: No {XGMTOML_EXT} files to process. You may have specified directories "
        "that don't contain any, or a wildcard that doesn't match any."
    )
    argparse_exit_if_no_paths(
        all_inpaths_toml, progname=parser.prog, errormessage=errormessage
    )

    # create outdir if it doesn't exist (now that we know we have at least 1 input file)
    outdir = parsed_args.directory
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    if parsed_args.verbose:
        # noinspection PyUnusedLocal
        def verbosefunc(contentsidx, num_contents, contentfile):
            print(f"  {contentfile.name16!r} ->")

    else:
        verbosefunc = None

    # process all input paths
    for inpath in all_inpaths_toml:
        # goal: in.XGM.toml -> in.XGM
        output_name = replaceext(os.path.basename(inpath), XGM_EXT, XGMTOML_EXT)
        output_path = os.path.join(outdir, output_name)

        # pack XGM container file
        if parsed_args.verbose:
            print(f"packing {inpath!r} -> {output_path!r}")
        xgm = read_toml(inpath)
        write_xgm(xgm, output_path, progressfunc=verbosefunc)


if __name__ == "__main__":
    main()
