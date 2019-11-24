#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extutils.py - utility functions for handling file extensions"""
import os

_d = os.path.extsep


class ExtensionError(ValueError):
    """error raised regarding path/filename extensions"""

    pass


def splitext(filepath, *considered_exts):
    """like os.path.splitext but also treat each ext as a single extension

    considered_exts: Each is a case insensitive extension that should be considered a
      single extension and  split off accordingly. e.g. if you pass .tar.gz, file.tar.gz
      splits to (file, .tar.gz) instead of (file.tar, .gz).
    raises ExtensionError if an ext doesn't begin with os.path.extsep`
    returns: tuple of (root, .ext); .ext can be empty string if there's none.
    """
    badexts = tuple(
        filter(lambda x: not str.startswith(x, os.path.extsep), considered_exts)
    )
    if badexts:
        raise ExtensionError(
            f"These extensions do not start with {os.path.extsep!r}: " f"{badexts!r}"
        )

    # ignore regular extensions that will be split off by os.path.splitext anyway
    multiexts = (x.lower() for x in considered_exts if x.count(os.path.extsep) > 1)
    for multiext in multiexts:
        if filepath.lower().endswith(multiext):
            extlen = len(multiext)
            root = filepath[:-extlen]
            ext = filepath[-extlen:]
            return root, ext
    return os.path.splitext(filepath)


def replaceext(filepath, new_ext, *considered_exts):
    """replace extension of filepath with new_ext

    filepath: a file path
    new_ext: extension the returned filepath should have (e.g ".ext")
    considered_exts: Each is a case insensitive extension that should be considered a
      single extension and replaced accordingly. e.g. if you pass .tar.gz, file.tar.gz
      becomes file.new_ext instead of file.tar.new_ext
    returns: filepath with its extension replaced
    """
    root = splitext(filepath, *considered_exts)[0]
    return root + new_ext


# === Audio: Subsong extension stuff ===

SUBSONG_FORMATS = {"subimc": f"{_d}sub{_d}imc", "wav": f"{_d}wav"}


def subsongtype(filepath):
    """return subsong type based on filepath extension's (case insensitive)

    return a key (string) from SUPPORTED_FORMATS, or raise ExtensionError if none match
    """
    ext = subsong_splitext(filepath)[1].lower()
    for subsongformat_type, subsongformat_ext in SUBSONG_FORMATS.items():
        if ext == subsongformat_ext.lower():
            return subsongformat_type

    exts = " ".join(repr(x) for x in SUBSONG_FORMATS.values())
    filename = os.path.basename(filepath)
    raise ExtensionError(
        f"subsong filename {filename!r} should have one of the extensions [{exts}], "
        f"not {ext!r}"
    )


def subsong_splitext(filepath):
    """like os.path.splitext but properly splits off subsong extensions like .sub.imc

    Case insensitive, i.e. .SUB.IMC is also split off properly
    """
    subsong_exts = SUBSONG_FORMATS.values()
    return splitext(filepath, *subsong_exts)


def subsong_replaceext(filepath, subsongformat_type):
    """replace extension of subsong filepath with another extension

    will properly replace subsong extensions like .sub.imc

    filepath: a file path
    subsongformat_type: a key from extutils.SUBSONG_FORMATS. Pass the one corresponding
      to the extension you want the returned filepath to have
    returns: filepath with its extension replaced
    """
    new_ext = SUBSONG_FORMATS[subsongformat_type]
    considered_exts = SUBSONG_FORMATS.values()
    return replaceext(filepath, new_ext, *considered_exts)


# === Audio: IMC container extension stuff ===

IMC_EXT = f"{_d}IMC"

IMCTOML_EXT = f"{_d}IMC{_d}toml"
IMCTOML_EXT_GLOB = f"*{_d}[iI][mM][cC]{_d}[tT][oO][mM][lL]"  # case insensitive
