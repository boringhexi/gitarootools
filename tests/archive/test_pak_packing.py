# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""test_pak_packing.py - test command line tools pakpack and pakunpack"""
import filecmp
from shlex import split as shlex_split

import tomlkit

from gitarootools.cmdline.pakpack import main as run_pakpack
from gitarootools.cmdline.pakunpack import main as run_pakunpack
from tests.common import make_contents2destdir, read_text

testdatapkg_parent = "tests.archive.test_pak_packing_data"


def test_pakunpack(tmpdir, capsys):
    """pakunpack -v -d tmpdir/actual_output -q *.SSQ -p *.PAK"""
    datapkg = f"{testdatapkg_parent}.unpack"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    pak_input_wildcard_arg = tmpdir.join("*.PAK")
    ssq_input_wildcard_arg = tmpdir.join("*.SSQ")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual pakunpack command
    args = (
        f'-v -d "{output_dir_arg!s}" '
        f'-q "{ssq_input_wildcard_arg}" -p "{pak_input_wildcard_arg}"'
    )
    run_pakunpack(shlex_split(args))

    # 3. check verbose stdout
    stdout_line1, stdout_rest = capsys.readouterr().out.split(sep="\n", maxsplit=1)
    assert stdout_line1.startswith("unpacking ")
    assert (
        stdout_rest
        == """\
  -> 'A.gmo'
  -> 'B.gmo'
  -> 'C.gmo'
"""
    )

    # 4. prepare paths for file & dir comparison
    actual_output_dir = tmpdir.join("actual_output", "unpack_PAK")
    expected_ouput_dir = tmpdir.join("expected_output")
    toml_actual_output_path = actual_output_dir.join("unpack.PAK.toml")
    toml_expected_output_path = expected_ouput_dir.join("unpack.PAK.toml")

    # 5. check that the expected and actual output files are identical
    cmpdirs = filecmp.dircmp(
        actual_output_dir, expected_ouput_dir, ignore=["unpack.PAK.toml"]
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


def test_pakpack(tmpdir, capsys):
    """pakpack -v -d tmpdir/actual_output tmpdir/pack*"""
    datapkg = f"{testdatapkg_parent}.pack"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("pack*")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual pakunpack command
    args = f'-v -d "{output_dir_arg!s}" "{input_wildcard_arg}"'
    run_pakpack(shlex_split(args))

    # 3. check verbose stdout
    stdout_line1, stdout_rest = capsys.readouterr().out.split(sep="\n", maxsplit=1)
    assert stdout_line1.startswith("packing ")
    assert (
        stdout_rest
        == """\
  'A.gmo' ->
  'B.gmo' ->
  'C.gmo' ->
"""
    )

    # 4. prepare paths for file comparison
    actual_output_path = tmpdir.join("actual_output", "pack.PAK")
    expected_ouput_path = tmpdir.join("expected_output.PAK")

    # 5. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_ouput_path, shallow=False)
