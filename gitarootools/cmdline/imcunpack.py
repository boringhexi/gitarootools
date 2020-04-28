#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""imcunpack.py - command-line tool to unpack IMC audio container files to TOML+.sub.imc

unpacks each .IMC container file to a subdirectory containing .sub.imc subsongs and a
toml file that can be used to repack them
"""

import argparse
import os
import sys
from glob import iglob
from itertools import chain

from gitarootools.audio.imccontainer import read_imc
from gitarootools.audio.imctoml import write_toml
from gitarootools.miscutils.cmdutils import make_check_input_path, wrap_argparse_desc
from gitarootools.miscutils.extutils import IMC_EXT, IMCTOML_EXT, SUBSONG_FORMATS


def build_argparser():
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Unpack {IMC_EXT} audio container files to directories. Each "
        f"unpacked dir contains subsongs and a {IMCTOML_EXT} file for later repacking"
    )
    parser.add_argument(
        metavar="INPUT_IMCFILE",
        nargs="+",
        dest="input_imcfiles",
        help=f"path to one or more {IMC_EXT} audio container files",
        type=make_check_input_path(IMC_EXT, disallowed_mext=SUBSONG_FORMATS["subimc"]),
        # .sub.imc counts as a single extension, rather than as .imc, and is therefore
        # disallowed. .sub.imc is a subsong, not an IMC container.
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTER_DIR",
        default="",  # current working directory
        dest="outer_dir",
        help=f"output directory in which each directory of subsongs + {IMCTOML_EXT} "
        "file  will be created. If not specified, use the current working directory",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        default="",
        metavar="SUFFIX",
        dest="suffix",
        help="Suffix to include in the name of each directory of subsongs and its "
        f"{IMCTOML_EXT} filename",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help=f"list {IMC_EXT} files and their subsongs as they are unpacked",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        f"""\
Examples:
  Example 1: Unpack a single {IMC_EXT} file
      {parser.prog} file{IMC_EXT}

  Example 2: Unpack multiple {IMC_EXT} files, list files as they are unpacked
      {parser.prog} -v file{IMC_EXT} file2{IMC_EXT}

  Example 3: Unpack multiple {IMC_EXT} files with a wildcard
      {parser.prog} *{IMC_EXT}

  By default, file{IMC_EXT} will unpack to file_IMC{s}file{IMCTOML_EXT}. You can \
customize the output dir and filenames:

  Example 4: Give output dir and file a suffix (e.g. _US results in \
file_US_IMC{s}file_US{IMCTOML_EXT})
      {parser.prog} -s _US file{IMC_EXT} file2{IMC_EXT}

  Example 5: Create unpacked dirs in different outer directory (e.g. unpack to \
outerdir{s}file_IMC{s})
      {parser.prog} -d outerdir file{IMC_EXT}"""
    )
    return parser


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""
    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    if parsed_args.verbose:
        # noinspection PyUnusedLocal
        def verbosefunc(ssidx, num_subsongs, csubsong):
            print(f"  -> {csubsong.name!r}")

    else:
        verbosefunc = None

    outer_dir = parsed_args.outer_dir
    inpaths = chain.from_iterable(
        iglob(inpath) for inpath in parsed_args.input_imcfiles
    )
    suf = parsed_args.suffix

    for inpath in inpaths:
        namebase = os.path.splitext(os.path.basename(inpath))[0]  # dir/file.IMC -> file
        output_dirpath = os.path.join(
            outer_dir, f"{namebase}{suf}_IMC"  # outer/file_suf_IMC/
        )
        output_tomlbase = f"{namebase}{suf}{IMCTOML_EXT}"  # file_suf.IMC.toml

        # unpack IMC container file
        if parsed_args.verbose:
            print(f"unpacking {inpath!r} -> {output_dirpath!r}")
        imcc = read_imc(inpath)
        write_toml(
            imcc, output_dirpath, output_tomlbase, progressfunc=verbosefunc,
        )


if __name__ == "__main__":
    main()
