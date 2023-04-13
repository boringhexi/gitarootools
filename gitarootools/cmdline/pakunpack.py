#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""pakunpack.py - command-line tool to unpack PAK container files to TOML+contents

unpacks each .PAK container file to a subdirectory containing its contents and a
toml file that can be used to repack them
"""

import argparse
import os
import sys
from glob import iglob
from itertools import chain, zip_longest

from gitarootools.archive.pakcontainer import read_pak
from gitarootools.archive.paktoml import write_pak_to_toml
from gitarootools.miscutils.cmdutils import make_check_input_path, wrap_argparse_desc
from gitarootools.miscutils.extutils import PAK_EXT, PAKTOML_EXT


def build_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Unpack {PAK_EXT} container files to directories. Each unpacked dir contains "
        f"the container's contents and a {PAKTOML_EXT} file for later repacking"
    )
    parser.add_argument(
        "-p",
        "--pak",
        required=True,
        metavar="INPUT_PAKFILE",
        nargs="+",
        dest="input_pakfiles",
        help=f"path to one or more {PAK_EXT} container files",
        type=make_check_input_path(PAK_EXT),
    )
    parser.add_argument(
        "-q",
        "--ssq",
        metavar="INPUT_SSQFILE",
        nargs="*",
        dest="input_ssqfiles",
        help=f"optional path to one or more to .SSQ files. Each contains filenames "
        "that will be used to name the extracted contents of the respective PAK file. ",
        type=make_check_input_path(".SSQ"),
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTER_DIR",
        default="",  # current working directory
        dest="outer_dir",
        help=f"output directory in which each directory of contents + {PAKTOML_EXT} "
        "file  will be created. If not specified, use the current working directory",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        default="",
        metavar="SUFFIX",
        dest="suffix",
        help="Suffix to include in the name of each directory of contents and its "
        f"{PAKTOML_EXT} filename",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="list PAK files and their contents as they are unpacked",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Unpack a single {PAK_EXT} file, using a SSQ file to name the contents
      {parser.prog} -q file.SSQ -p file{PAK_EXT}

  Example 2: Unpack multiple {PAK_EXT} files, using multiple SSQ files
      {parser.prog} -q file.SSQ file2.SSQ -p file{PAK_EXT} file2{PAK_EXT}

  Example 3: Unpack multiple {PAK_EXT} files with a wildcard, list files as they are \
unpacked
      {parser.prog} -v -p *{PAK_EXT}

  By default, file{PAK_EXT} will unpack to file_PAK{s}file{PAKTOML_EXT} You can \
customize the output dir and filenames:

  Example 4: Give output dir and file a suffix (e.g. _US results in \
file_US_PAK{s}file_US{PAKTOML_EXT}
      {parser.prog} -s _US -p file{PAK_EXT} file2{PAK_EXT}

  Example 5: Create unpacked dirs in different outer directory (e.g. unpack to \
outerdir{s}file_PAK{s})
      {parser.prog} -d outerdir -p file{PAK_EXT}"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""
    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    if parsed_args.verbose:
        # noinspection PyUnusedLocal
        def verbosefunc(contentsidx, num_contents, contentfile):
            print(f"  -> {contentfile.name!r}")

    else:
        verbosefunc = None

    outer_dir = parsed_args.outer_dir
    inpaths = chain.from_iterable(
        iglob(inpath) for inpath in parsed_args.input_pakfiles
    )
    if parsed_args.input_ssqfiles is not None:
        ssqpaths = chain.from_iterable(
            iglob(ssqpath) for ssqpath in parsed_args.input_ssqfiles
        )
    else:
        ssqpaths = []
    suf = parsed_args.suffix

    for inpath, ssqpath in zip_longest(inpaths, ssqpaths):
        namebase = os.path.splitext(os.path.basename(inpath))[0]  # dir/file.PAK -> file
        output_dirpath = os.path.join(
            outer_dir, f"{namebase}{suf}_PAK"  # outer/file_suf_PAK/
        )
        output_tomlbase = f"{namebase}{suf}{PAKTOML_EXT}"  # file_suf.PAK.toml

        # unpack PAK container file
        if parsed_args.verbose:
            print(f"unpacking {inpath!r} -> {output_dirpath!r}")
        pakc = read_pak(inpath, ssqfile_or_path=ssqpath)
        write_pak_to_toml(
            pakc, output_dirpath, output_tomlbase, progressfunc=verbosefunc,
        )


if __name__ == "__main__":
    main()
