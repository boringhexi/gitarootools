#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imcpack.py - command-line tool to pack TOML+.sub.imc into IMC audio container files

Can take a specially written TOML file and its subsongs, and pack it into an IMC audio
container file.
"""
import argparse
import os
import sys

from gitarootools.audio.imccontainer import write_imc
from gitarootools.audio.imctoml import read_toml
from gitarootools.miscutils.cmdutils import (
    exit_if_no_paths,
    glob_all,
    glob_all_dirs_to_wildcards,
    charunwrap,
    wrap_argparse_desc,
)
from gitarootools.miscutils.extutils import (
    IMC_EXT,
    IMCTOML_EXT,
    IMCTOML_EXT_GLOB,
    replaceext,
)


def build_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.description = wrap_argparse_desc(
        f"Pack {IMCTOML_EXT} files and their subsongs into {IMC_EXT} "
        "audio container files"
    )
    parser.add_argument(
        metavar="INPUT_PATH",
        nargs="+",
        dest="input_paths",
        help=f"one or more input paths. Each can be a {IMCTOML_EXT} file or a "
        f"directory containing at least one {IMCTOML_EXT} file. Directories without a "
        f"{IMCTOML_EXT} file will be skipped",
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="OUTDIR",
        default="",  # current working directory
        dest="directory",
        help="directory to which each .IMC file will be written "
        "(uses the current working directory if not specified)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="list files and subsongs as they are packed",
    )
    s = os.path.sep
    parser.epilog = wrap_argparse_desc(
        charunwrap(  # Using > as a line continuation character
            f"""\
Examples:
  Example 1: Pack a single {IMCTOML_EXT} file
      {parser.prog} ST00A{IMCTOML_EXT}

  Example 2: Pack all {IMCTOML_EXT} files in the chosen directories, list files as they
  >are packed
      {parser.prog} -v ST00A{s} ST00B{s}

  Example 3: Pack any {IMCTOML_EXT} files in the current directory
      {parser.prog} {os.curdir}

  Example 4: Use a wildcard to search multiple directories for {IMCTOML_EXT} files and
  >pack them
      {parser.prog} STAGE*{s}

  Example 5: Write packed {IMC_EXT} files to a different directory
      {parser.prog} -d mystuff{s} ST00A{IMCTOML_EXT}"""
        )
    )
    return parser


def main(args=sys.argv[1:]):
    """args: sequence of command line argument strings"""

    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    # get all input paths, convert all dirs to *.IMC.toml paths if they contain any
    all_inpaths = glob_all(parsed_args.input_paths)
    all_inpaths_toml = glob_all_dirs_to_wildcards(all_inpaths, IMCTOML_EXT_GLOB)

    # or exit with an error if there aren't any matching paths
    errorprefix = f"{parser.prog}: " if parser.prog else ""
    errormessage = (
        f"error: No {IMCTOML_EXT} files to process. You may have specified directories "
        "that don't contain any, or a wildcard that doesn't match any"
    )
    exit_if_no_paths(
        all_inpaths_toml, errorprefix=errorprefix, errormessage=errormessage
    )

    # create outdir if it doesn't exist (now that we know we have at least 1 input file)
    outdir = parsed_args.directory
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    if parsed_args.verbose:
        # noinspection PyUnusedLocal
        def verbosefunc(ssidx, num_subsongs, csubsong):
            print(f"  {csubsong.name!r} ->")

    else:
        verbosefunc = None

    # process all input paths
    for inpath in all_inpaths_toml:
        # goal: in.IMC.toml -> in.IMC
        output_name = replaceext(os.path.basename(inpath), IMC_EXT, IMCTOML_EXT)
        output_path = os.path.join(outdir, output_name)

        # pack IMC container file
        if parsed_args.verbose:
            print(f"packing {inpath!r} -> {output_path!r}")
        imcc = read_toml(inpath)
        write_imc(imcc, output_path, progressfunc=verbosefunc)


if __name__ == "__main__":
    main()
