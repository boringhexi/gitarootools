#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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


def exit_if_no_paths(
    seq,
    errorprefix="",
    errormessage="error: No files to process. You may have specified a wildcard "
    "that doesn't match anything",
):
    """if seq is empty, print errorprefix+errormessage and do sys.exit(2)"""
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


def charunwrap(text, char=">"):
    """any line starting with char is appended to the previous line

    if a line in text starts with char (or whitespace then char), it is assumed to be a
    continuation of the previous line and will be appended (with a space) to the
    previous line.
    returns: (str) text with those lines unwrapped
    """
    unwrapped_lines = []
    current_lineparts = []
    end = ""
    for line, line_end in zip(text.splitlines(), text.splitlines(keepends=True)):
        prev_end = end
        end = line_end[len(line) :]
        line_lstrip = line.lstrip()
        if line_lstrip.startswith(char):
            # starts with char, so append to previous
            current_lineparts.append(line_lstrip[len(char) :])
        elif current_lineparts:
            # starting a new line, done adding to the previous one
            unwrapped_lines.append(" ".join(current_lineparts) + prev_end)
            current_lineparts = [line]
        else:
            # just starting out
            current_lineparts = [line]
    unwrapped_lines.append(" ".join(current_lineparts) + end)
    return "".join(unwrapped_lines)


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
