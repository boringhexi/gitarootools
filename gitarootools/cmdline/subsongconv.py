#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subsongconv.py - command-line tool to convert one subsong to any format/filename"""
import argparse
import sys

from gitarootools.audio.subsong import read_subsong, write_subsong
from gitarootools.miscutils.cmdutils import make_check_input_path
from gitarootools.miscutils.extutils import SUBSONG_FORMATS


def build_argparser():
    supported_extensions = SUBSONG_FORMATS.values()
    parser = argparse.ArgumentParser(
        description="Convert a single subsong to any format and filename. "
        f"Supported formats include: {', '.join(supported_extensions)}"
    )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true")
    parser.add_argument(
        "input_subsong",
        help=f"path of input subsong file, e.g. intro{SUBSONG_FORMATS['subimc']}",
        type=make_check_input_path(*supported_extensions),
    )
    parser.add_argument(
        "output_subsong",
        help=f"path of output subsong file, e.g. intro{SUBSONG_FORMATS['wav']}",
        type=make_check_input_path(*supported_extensions),
    )
    return parser


def main(args=sys.argv[1:]):
    parser = build_argparser()
    parsed_args = parser.parse_args(args)

    inpath, outpath = parsed_args.input_subsong, parsed_args.output_subsong
    if parsed_args.verbose:
        print(f"converting {inpath!r} -> {outpath!r}")
    subsong = read_subsong(inpath)
    write_subsong(subsong, outpath)


if __name__ == "__main__":
    main()
