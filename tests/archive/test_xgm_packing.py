#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""test_xgmpacking.py - test command line tools xgmpack and xgmunpack"""


import filecmp
from shlex import split as shlex_split

import tomlkit

from gitarootools.cmdline.xgmpack import main as run_xgmpack
from gitarootools.cmdline.xgmunpack import main as run_xgmunpack
from tests.common import make_contents2destdir, read_text

testdatapkg_parent = "tests.archive.test_xgm_packing_data"


def test_xgmunpack(tmpdir, capsys):
    """xgmunpack -d tmpdir/actual_output *.XGM"""
    datapkg = f"{testdatapkg_parent}.unpack"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("*.XGM")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual xgmunpack command
    args = f'-v -d "{output_dir_arg!s}" "{input_wildcard_arg}"'
    run_xgmunpack(shlex_split(args))

    # 3. check verbose stdout
    stdout_line1, stdout_rest = capsys.readouterr().out.split(sep="\n", maxsplit=1)
    assert stdout_line1.startswith("unpacking ")
    assert (
        stdout_rest
        == """\
  -> 'A.IMX'
  -> 'B.IMX'
  -> 'C.XG'
  -> 'D.XG'
  -> 'E.XG'
"""
    )

    # 4. prepare paths for file & dir comparison
    actual_output_dir = tmpdir.join("actual_output", "unpack_XGM")
    expected_ouput_dir = tmpdir.join("expected_output")
    toml_actual_output_path = actual_output_dir.join("unpack.XGM.toml")
    toml_expected_output_path = expected_ouput_dir.join("unpack.XGM.toml")

    # 5. check that the expected and actual output files are identical
    cmpdirs = filecmp.dircmp(
        actual_output_dir, expected_ouput_dir, ignore=["unpack.XGM.toml"]
    )
    match, mismatch, errors = filecmp.cmpfiles(
        actual_output_dir, expected_ouput_dir, cmpdirs.common, shallow=False
    )
    assert not mismatch
    assert not errors
    # In the case of toml files, compares just values, not comments and such
    toml_actual_output = tomlkit.parse(read_text(toml_actual_output_path))
    toml_expected_output = tomlkit.parse(read_text(toml_expected_output_path))
    # before comparing, remove the guide/help section if it exists
    toml_actual_output.pop("Help/Guide", None)
    toml_expected_output.pop("Help/Guide", None)
    assert toml_actual_output == toml_expected_output


def test_xgmpack(tmpdir, capsys):
    """xgmpack -d tmpdir/actual_output tmpdir/pack*"""
    datapkg = f"{testdatapkg_parent}.pack"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("pack*")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual xgmunpack command
    args = f'-v -d "{output_dir_arg!s}" "{input_wildcard_arg}"'
    run_xgmpack(shlex_split(args))

    # 3. check verbose stdout
    stdout_line1, stdout_rest = capsys.readouterr().out.split(sep="\n", maxsplit=1)
    assert stdout_line1.startswith("packing ")
    assert (
        stdout_rest
        == """\
  'A.IMX' ->
  'B.IMX' ->
  'C.XG' ->
  'D.XG' ->
  'E.XG' ->
"""
    )

    # 4. prepare paths for file comparison
    actual_output_path = tmpdir.join("actual_output", "pack.XGM")
    expected_ouput_path = tmpdir.join("expected_output.XGM")

    # 5. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_ouput_path, shallow=False)
