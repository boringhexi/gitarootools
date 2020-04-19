# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""test_subsong_conversion.py - test command line tools subsongconv, subsong2wav,
subsong2subimc
"""

import filecmp
from shlex import split as shlex_split

from gitarootools.cmdline.subsong2subimc import main as run_subsong2subimc
from gitarootools.cmdline.subsong2wav import main as run_subsong2wav
from gitarootools.cmdline.subsongconv import main as run_subsongconv
from tests.common import make_resource2destdir

testdatapkg_parent = "tests.audio.test_subsong_conversion_data"


def test_subsongconv_subimc2wav(tmpdir):
    """subsongconv input.sub.imc output.wav"""
    datapkg = f"{testdatapkg_parent}.subimc2wav"
    resource2tmpdir = make_resource2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    input_path = resource2tmpdir("input.sub.imc")
    expected_output_path = resource2tmpdir("expected_output.wav")
    actual_output_path = tmpdir.join("actual_output.wav")

    # 2. run the actual subsongconv command
    args = f'"{input_path!s}" "{actual_output_path!s}"'
    run_subsongconv(shlex_split(args))

    # 3. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_output_path, shallow=False)


def test_subsongconv_wav2subimc(tmpdir):
    """subsongconv input.wav output.sub.imc"""
    datapkg = f"{testdatapkg_parent}.wav2subimc"
    resource2tmpdir = make_resource2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    input_path = resource2tmpdir("input.wav")
    expected_output_path = resource2tmpdir("expected_output.sub.imc")
    actual_output_path = tmpdir.join("actual_output.sub.imc")

    # 2. run the actual subsongconv command
    args = f'"{input_path!s}" "{actual_output_path!s}"'
    run_subsongconv(shlex_split(args))

    # 3. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_output_path, shallow=False)


def test_subsong2wav_subimc2wav(tmpdir):
    """subsong2wav -d tmpdir *.sub.imc"""
    datapkg = f"{testdatapkg_parent}.subimc2wav"
    resource2tmpdir = make_resource2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    resource2tmpdir("input.sub.imc")  # will be loaded by input_wildcard_path
    input_wildcard_path = tmpdir.join("*.sub.imc")
    expected_output_path = resource2tmpdir("expected_output.wav")
    actual_output_dir_path = tmpdir.join("actual_output")
    actual_output_path = actual_output_dir_path.join("input.wav")

    # 2. run the actual subsong2wav command
    args = f'-d "{actual_output_dir_path!s}" "{input_wildcard_path!s}"'
    run_subsong2wav(shlex_split(args))

    # 3. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_output_path, shallow=False)


def test_subsong2subimc_wav2subimc(tmpdir):
    """subsong2wav -d tmpdir *.wav"""
    datapkg = f"{testdatapkg_parent}.wav2subimc"
    resource2tmpdir = make_resource2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    resource2tmpdir("input.wav")  # will be loaded by input_wildcard_path
    input_wildcard_path = tmpdir.join("*.wav")
    expected_output_path = resource2tmpdir("expected_output.sub.imc")
    actual_output_dir_path = tmpdir.join("actual_output")
    actual_output_path = actual_output_dir_path.join("input.sub.imc")

    # 2. run the actual subsongconv command
    args = f'-d "{actual_output_dir_path!s}" "{input_wildcard_path!s}"'
    run_subsong2subimc(shlex_split(args))

    # 3. check that the expected and actual output files are identical
    assert filecmp.cmp(actual_output_path, expected_output_path, shallow=False)
