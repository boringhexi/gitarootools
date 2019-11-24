#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_imcpacking.py - test command line tools imcpack and imcunpack"""

import filecmp
from shlex import split as shlex_split

import tomlkit

from gitarootools.cmdline.imcpack import main as run_imcpack
from gitarootools.cmdline.imcunpack import main as run_imcunpack
from tests.common import make_contents2destdir, read_text

testdatapkg_parent = "tests.audio.test_imc_packing_data"


def test_imcunpack(tmpdir, capsys):
    """imcunpack -d tmpdir/actual_output *.IMC"""
    datapkg = f"{testdatapkg_parent}.unpack"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("*.IMC")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual imcunpack command
    args = f'-v -d "{output_dir_arg!s}" "{input_wildcard_arg}"'
    run_imcunpack(shlex_split(args))

    # 3. check verbose stdout
    stdout_line1, stdout_rest = capsys.readouterr().out.split(sep="\n", maxsplit=1)
    assert stdout_line1.startswith("unpacking ")
    assert (
        stdout_rest
        == """\
  -> 'apple1'
  -> 'apple2'
"""
    )

    # 4. prepare paths for file & dir comparison
    actual_output_dir = tmpdir.join("actual_output", "unpack")
    expected_ouput_dir = tmpdir.join("expected_output")
    toml_actual_output_path = actual_output_dir.join("unpack.IMC.toml")
    toml_expected_output_path = expected_ouput_dir.join("unpack.IMC.toml")

    # 5. check that the expected and actual output files are identical
    cmpdirs = filecmp.dircmp(
        actual_output_dir, expected_ouput_dir, ignore=["unpack.IMC.toml"]
    )
    match, mismatch, errors = filecmp.cmpfiles(
        actual_output_dir, expected_ouput_dir, cmpdirs.common, shallow=False
    )
    assert not mismatch
    assert not errors
    # In the case of toml files, compares just values, not comments and such
    toml_actual_output = tomlkit.parse(read_text(toml_actual_output_path))
    toml_expected_output = tomlkit.parse(read_text(toml_expected_output_path))
    assert toml_actual_output == toml_expected_output


def test_imcpack(tmpdir, capsys):
    """imcpack -d tmpdir/actual_output tmpdir/pack*"""
    datapkg = f"{testdatapkg_parent}.pack"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("pack*")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual imcunpack command
    args = f'-v -d "{output_dir_arg!s}" "{input_wildcard_arg}"'
    run_imcpack(shlex_split(args))

    # 3. check verbose stdout
    stdout_line1, stdout_rest = capsys.readouterr().out.split(sep="\n", maxsplit=1)
    assert stdout_line1.startswith("packing ")
    assert (
        stdout_rest
        == """\
  'Chorus' ->
  'DrumsLeft' ->
  'DrumsRight' ->
  'DrumsLChorusR' ->
"""
    )

    # 4. prepare paths for file comparison
    actual_output_path = tmpdir.join("actual_output", "pack.IMC")
    expected_ouput_path = tmpdir.join("expected_output.IMC")

    # 5. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_ouput_path, shallow=False)
