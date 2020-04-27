#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""xgmunpack.py - command-line tool to unpack XGM container files to TOML+contents

unpacks each .XGM container file to a subdirectory containing its contents and a
toml file that can be used to repack them
"""

import argparse
import os
import sys
from glob import iglob
from itertools import chain

from gitarootools.archive.xgmcontainer import read_xgm
from gitarootools.archive.xgmtoml import write_toml
from gitarootools.miscutils.cmdutils import make_check_input_path, wrap_argparse_desc
from gitarootools.miscutils.extutils import XGM_EXT, XGMTOML_EXT


def build_argparser():
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Unpack {XGM_EXT} container files to directories. Each unpacked dir contains "
        f"the container's contents and a {XGMTOML_EXT} file for later repacking"
    )
    parser.add_argument(
        metavar="INPUT_XGMFILE",
        nargs="+",
        dest="input_xgmfiles",
        help=f"path to one or more {XGM_EXT} container files",
        type=make_check_input_path(XGM_EXT),
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTER_DIR",
        default="",  # current working directory
        dest="outer_dir",
        help=f"output directory in which each directory of contents + {XGMTOML_EXT} "
        "file  will be created. If not specified, use the current working directory",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        default="",
        metavar="SUFFIX",
        dest="suffix",
        help="Suffix to include in the name of each directory of contents and its "
        f"{XGMTOML_EXT} filename",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="list XGM files and their contents as they are unpacked",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Unpack a single {XGM_EXT} file
      {parser.prog} file{XGM_EXT}

  Example 2: Unpack multiple {XGM_EXT} files, list files as they are unpacked
      {parser.prog} -v file{XGM_EXT} file2{XGM_EXT}

  Example 3: Unpack multiple {XGM_EXT} files with a wildcard
      {parser.prog} *{XGM_EXT}

  By default, file{XGM_EXT} will unpack to file_XGM{s}file{XGMTOML_EXT} You can \
customize the output dir and filenames:

  Example 4: Give output dir and file a suffix (e.g. _US results in \
file_US_XGM{s}file_US{XGMTOML_EXT}
      {parser.prog} -s _US file{XGM_EXT} file2{XGM_EXT}

  Example 5: Create unpacked dirs in different outer directory (e.g. unpack to \
outerdir{s}file_IMC{s})
      {parser.prog} -d outerdir file{XGM_EXT}"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""
    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    if parsed_args.verbose:
        # noinspection PyUnusedLocal
        def verbosefunc(contentsidx, num_contents, contentfile):
            print(f"  -> {contentfile.name16!r}")

    else:
        verbosefunc = None

    outer_dir = parsed_args.outer_dir
    inpaths = chain.from_iterable(
        iglob(inpath) for inpath in parsed_args.input_xgmfiles
    )
    suf = parsed_args.suffix

    for inpath in inpaths:
        namebase = os.path.splitext(os.path.basename(inpath))[0]  # dir/file.XGM -> file
        output_dirpath = os.path.join(
            outer_dir, f"{namebase}{suf}_XGM"  # outer/file_suf_XGM/
        )
        output_tomlbase = f"{namebase}{suf}{XGMTOML_EXT}"  # file_suf.XGM.toml

        # unpack XGM container file
        if parsed_args.verbose:
            print(f"unpacking {inpath!r} -> {output_dirpath!r}")
        xgmc = read_xgm(inpath)
        write_toml(
            xgmc, output_dirpath, output_tomlbase, progressfunc=verbosefunc,
        )


if __name__ == "__main__":
    main()
