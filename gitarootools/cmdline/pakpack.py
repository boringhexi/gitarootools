#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""pakpack.py - command-line tool to pack PAK TOML+contents into PAK container files

Can take a specially written TOML file + PAK contents and pack them into an
PAK container file.
"""

import argparse
import os
import sys

from gitarootools.archive.pakcontainer import write_pak
from gitarootools.archive.paktoml import read_pak_from_toml
from gitarootools.miscutils.cmdutils import (
    argparse_exit_if_no_paths,
    glob_all,
    glob_all_dirs_to_wildcards,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import (
    PAK_EXT,
    PAKTOML_EXT,
    PAKTOML_EXT_GLOB,
    replaceext,
)


def build_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Pack {PAKTOML_EXT} files and their contents into {PAK_EXT} " "container files"
    )
    parser.add_argument(
        metavar="INPUT_PATH",
        nargs="+",
        dest="input_paths",
        help=f"one or more input paths. Each can be a {PAKTOML_EXT} file or a "
        f"directory containing at least one {PAKTOML_EXT} file. Directories without a "
        f"{PAKTOML_EXT} file will be skipped",
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTDIR",
        default="",  # current working directory
        dest="directory",
        help=f"directory to which each {PAK_EXT} file will be written "
        "(uses the current working directory if not specified)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help=f"list {PAK_EXT} files and their contents as they are packed",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Pack a single {PAKTOML_EXT} file
      {parser.prog} file{PAKTOML_EXT}

  Example 2: Pack any {PAKTOML_EXT} files in the current directory
      {parser.prog} {os.curdir}

  Example 3: Pack all {PAKTOML_EXT} files in the chosen directories, list files as \
they are packed
      {parser.prog} -v file{s} file2{s}

  Example 4: Use a wildcard to search multiple directories for {PAKTOML_EXT} files and \
pack them
      {parser.prog} STAGE*{s}

  Example 5: Write packed {PAK_EXT} files to a different directory
      {parser.prog} -d outdir file{PAKTOML_EXT}"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""

    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    # get all input paths, convert all dirs to *.PAK.toml paths if they contain any
    all_inpaths = glob_all(parsed_args.input_paths)
    all_inpaths_toml = glob_all_dirs_to_wildcards(all_inpaths, PAKTOML_EXT_GLOB)

    # or exit with an error if there aren't any matching paths
    errormessage = (
        f"error: No {PAKTOML_EXT} files to process. You may have specified directories "
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
            print(f"  {contentfile.name!r} ->")

    else:
        verbosefunc = None

    # process all input paths
    for inpath in all_inpaths_toml:
        # goal: in.PAK.toml -> in.PAK
        output_name = replaceext(os.path.basename(inpath), PAK_EXT, PAKTOML_EXT)
        output_path = os.path.join(outdir, output_name)

        # pack PAK container file
        if parsed_args.verbose:
            print(f"packing {inpath!r} -> {output_path!r}")
        pak = read_pak_from_toml(inpath)
        write_pak(pak, output_path, progressfunc=verbosefunc)


if __name__ == "__main__":
    main()
