#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from gitarootools.miscutils.cmdutils import (
    make_check_input_path,
    charunwrap,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import IMC_EXT, IMCTOML_EXT, SUBSONG_FORMATS


def build_argparser():
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
        help="Suffix to append to the name of each directory of subsongs and its "
        f"{IMCTOML_EXT} filename",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="list files and subsongs as they are unpacked",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        charunwrap(  # Using > as a line continuation character
            f"""\
Examples:
  Example 1: Unpack a single {IMC_EXT} file
      {parser.prog} ST00A.IMC

  Example 2: Unpack multiple {IMC_EXT} files, list files as they are unpacked
      {parser.prog} -v ST00A{IMC_EXT} ST00B{IMC_EXT}

  Example 3: Unpack multiple {IMC_EXT} files with a wildcard
      {parser.prog} *{IMC_EXT}

  Example 4: Give output directories a suffix (e.g. ST00A_US{s})
      {parser.prog} -s _US ST00A{IMC_EXT} ST00B{IMC_EXT}

  Example 5: Create unpacked dirs in different directory (e.g. create ST00A{s} in
  >mystuff{s})
      {parser.prog} -d mystuff{s} ST00A{IMC_EXT}"""
        )
    )
    return parser


def main(args=sys.argv[1:]):
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
    for inpath in inpaths:
        output_name = os.path.splitext(os.path.basename(inpath))[0]
        output_name += parsed_args.suffix  # e.g. ST00A_suffix

        # unpack IMC container file
        if parsed_args.verbose:
            print(f"unpacking {inpath!r} -> {os.path.join(outer_dir, output_name)!r}")
        imcc = read_imc(inpath)
        write_toml(imcc, output_name, outer_dir, progressfunc=verbosefunc)


if __name__ == "__main__":
    main()
