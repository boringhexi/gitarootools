# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""cmdutils.py - utility functions for command line stuff"""


import argparse
import os
import sys
from glob import iglob
from itertools import chain
from shutil import get_terminal_size
from textwrap import fill

from gitarootools.miscutils.extutils import splitext


def glob_all(paths):
    """return tuple of glob matches of all paths"""
    return tuple(chain.from_iterable(iglob(inpath) for inpath in paths))


def glob_all_dirs_to_wildcards(paths, *dir_wildcards):
    """return paths with every dir path converted to dirpath/+wildcard and globbed

    Effectively, search all dirs for files matching dir_wildcards, but don't change
    existing paths to actual files

    paths: an iterable of paths
    dir_wildcards: each is a filename glob pattern, e.g. "*.wav"

    Any file path will be returned as-is.
    Any directory path will be changed to dir/+dir_wildcard and globbed
      e.g. dir + *.wav can become: dir/1.wav, dir/2.wav if those files exist

    returns: a list of paths, all of which now point to files, not dirs
    """
    wildcarded_paths = []
    for path in paths:
        if os.path.isdir(path):
            for dir_wildcard in dir_wildcards:
                dirmatches = iglob(os.path.join(path, dir_wildcard))
                wildcarded_paths.extend(dirmatches)
        else:
            wildcarded_paths.append(path)
    return wildcarded_paths


def argparse_exit_if_no_paths(
    seq,
    progname=None,
    errormessage="error: No files to process. You may have specified a wildcard "
    "that doesn't match anything.",
):
    """if seq is empty, print progname+errormessage to stderr and do sys.exit(2)

    So named because it behaves like argparse's usage errors and is meant to be used
    alongside it.

    :param seq: sequence. if empty, print the error and exit
    :param progname: name of this program, can be None/empty string
    :param errormessage: error message to print
    :return:
    """
    if not progname:
        progname = os.path.basename(sys.argv[0])
    errorprefix = f"{progname}: " if progname else ""
    if not seq:
        print(errorprefix + errormessage, file=sys.stderr)
        sys.exit(2)


def make_check_input_path(
    *allowed_extensions, disallowed_mext=None, disallowed_mexts=tuple()
):
    """return an argparse type-checking func to verify a path has an allowed extension

    allowed_extensions: path must have one of these extensions, or else the returned
      func will consider it invalid and raise an argparse ArgumentTypeError
    disallowed_mext: disallow this multi-extension (e.g. .tar.gz) even if its last part
      is an allowed extension. e.g. you can allow file.gz and disallow file.tar.gz
    disallowed_mexts: or instead, you can pass an sequence of many disallowed_mext args

    All extension-matching (to allowed, disallowed) is case-insensitive.
    returns a function suitable to be passed as `type` in parser.add_argument(type=...)
    """
    disallowed_mext = tuple() if disallowed_mext is None else (disallowed_mext,)

    def check_input_path(filepath):
        """verifies that filepath has a valid extension"""
        ext = splitext(
            filepath, *disallowed_mext, *disallowed_mexts, *allowed_extensions
        )[1]
        if ext.lower() not in map(str.lower, allowed_extensions):
            filename = os.path.basename(filepath)
            if len(allowed_extensions) == 1:
                raise argparse.ArgumentTypeError(
                    f"filename {filename!r} must have extension "
                    f"{allowed_extensions[0]!r}, not {ext!r}"
                )
            else:
                raise argparse.ArgumentTypeError(
                    f"filename {filename!r} must have one of the extensions "
                    f"[{', '.join(repr(x) for x in allowed_extensions)}]"
                    f"not {ext!r}"
                )
        return filepath

    return check_input_path


def wrap_argparse_desc(text, width=None):
    """wrap text to width (or current terminal width - 2)

    - This wraps lines much like argparse. This means if you have an argparse parser
      using RawDescriptionHelpFormatter and you want to wrap text to the console window
      while keeping newlines intact, you can pre-wrap the description/epilog with this
      before passing it to the parser
    - any new lines created from a line keep the original line's indent.
    """
    if width is None:
        # like argparse
        width = get_terminal_size().columns - 2
        width = max(11, width)

    rettext = []
    for line in text.splitlines(keepends=True):
        indent = line[: len(line) - len(line.lstrip())]
        rettext.append(fill(line, width=width, subsequent_indent=indent))
    return "\n".join(rettext)


def my_warn(message) -> None:
    """print message to stderr as an orange-colored warning

    :param message:
    :return:
    """
    print(f"\033[93m{message!s}\033[0m", file=sys.stderr)
