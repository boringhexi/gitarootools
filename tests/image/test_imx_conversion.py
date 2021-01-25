# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""test_imx_conversion.py - test command line tools imx2png, png2imx"""
import os
from glob import glob
from shlex import split as shlex_split

from gitarootools.cmdline.imx2png import main as run_imx2png
from gitarootools.cmdline.png2imx import main as run_png2imx
from tests.common import images_identical, imx_images_identical, make_contents2destdir

testdatapkg_parent = "tests.image.test_imx_conversion_data"


def test_imx2png(tmpdir, capsys):
    """imx2png -v -d tmpdir/actual_output *.IMX"""
    datapkg = f"{testdatapkg_parent}.imx2png"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("*.IMX")
    output_dir_arg = tmpdir.join("actual_output")

    # 2. run the actual imx2png command
    args = f'-v -d "{output_dir_arg}" "{input_wildcard_arg}"'
    run_imx2png(shlex_split(args))

    # 3. check verbose stdout
    # note: checking stdout for filenames has little use since later the output files
    # are later checked against expected output filenames. May as well delete this
    stdout_lines = [line for line in capsys.readouterr().out.split("\n") if line]
    stdout_filenames = [os.path.basename(shlex_split(line)[3]) for line in stdout_lines]
    assert set(stdout_filenames) == {
        "cc0_alpha_i4.i4.png",
        "cc0_alpha_i8.i8.png",
        "cc0_alpha_rgba32.rgba32.png",
        "cc0_opaque_i4.i4.png",
        "cc0_opaque_i8.i8.png",
        "cc0_opaque_rgb24.rgb24.png",
        "cc0_opaque_rgba32.rgba32.png",
    }

    # 4. prepare paths for file & dir comparison
    actual_output_dir = output_dir_arg
    expected_output_dir = tmpdir.join("expected_output")
    actual_pngs = glob(str(actual_output_dir.join("*.png")))
    expected_pngs = glob(str(expected_output_dir.join("*.png")))

    # 5. Compare actual output PNGs to expected output PNGs
    assert len(actual_pngs) == len(expected_pngs)
    for actualpng, expectedpng in zip(sorted(actual_pngs), sorted(expected_pngs)):
        assert os.path.basename(actualpng) == os.path.basename(expectedpng)
        assert images_identical(actualpng, expectedpng)


def test_png2imx_opaque(tmpdir, capsys):
    """png2imx -v -d tmpdir/actual_output cc0_opaque.*.png"""
    datapkg = f"{testdatapkg_parent}.png2imx"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("cc0_opaque.*.png")
    output_dir_arg = tmpdir.join("actual_output_opaque")

    # 2. run the actual imx2png command
    args = f'-v -d "{output_dir_arg}" "{input_wildcard_arg}"'
    run_png2imx(shlex_split(args))

    # 3. check verbose stdout
    stdout_lines = [line for line in capsys.readouterr().out.split("\n") if line]
    stdout_filenames = [os.path.basename(shlex_split(line)[3]) for line in stdout_lines]
    assert set(stdout_filenames) == {
        "cc0_opaque.i4.IMX",
        "cc0_opaque.i8.IMX",
        "cc0_opaque.rgb24.IMX",
        "cc0_opaque.rgba32.IMX",
        "cc0_opaque.auto_i4.IMX",
        "cc0_opaque.auto_i8.IMX",
        "cc0_opaque.auto_rgb24.IMX",
    }

    # 4. prepare paths for file & dir comparison
    actual_output_dir = output_dir_arg
    expected_output_dir = tmpdir.join("expected_output_opaque")
    actual_imxs = glob(str(actual_output_dir.join("*.IMX")))
    expected_imxs = glob(str(expected_output_dir.join("*.IMX")))

    # 5. Compare actual output IMXs to expected output IMXs
    assert len(actual_imxs) == len(expected_imxs)
    for actualimx, expectedimx in zip(sorted(actual_imxs), sorted(expected_imxs)):
        assert os.path.basename(actualimx) == os.path.basename(expectedimx)
        assert imx_images_identical(actualimx, expectedimx)


def test_png2imx_alpha(tmpdir, capsys):
    """png2imx -v -d tmpdir/actual_output cc0_alpha.*.png"""
    datapkg = f"{testdatapkg_parent}.png2imx"
    contents2tmpdir = make_contents2destdir(datapkg, tmpdir)

    # 1. prepare data files & paths
    contents2tmpdir(recursive=True)
    input_wildcard_arg = tmpdir.join("cc0_alpha.*.png")
    output_dir_arg = tmpdir.join("actual_output_alpha")

    # 2. run the actual imx2png command
    args = f'-v -d "{output_dir_arg}" "{input_wildcard_arg}"'
    run_png2imx(shlex_split(args))

    # 3. check verbose stdout
    stdout_lines = [line for line in capsys.readouterr().out.split("\n") if line]
    stdout_filenames = [os.path.basename(shlex_split(line)[3]) for line in stdout_lines]
    assert set(stdout_filenames) == {
        "cc0_alpha.auto_i4.IMX",
        "cc0_alpha.auto_i8.IMX",
        "cc0_alpha.auto_rgba.IMX",
        "cc0_alpha.i4.IMX",
        "cc0_alpha.i8.IMX",
        "cc0_alpha.rgb24.IMX",
        "cc0_alpha.rgba32.IMX",
    }

    # 4. prepare paths for file & dir comparison
    actual_output_dir = output_dir_arg
    expected_output_dir = tmpdir.join("expected_output_alpha")
    actual_imxs = glob(str(actual_output_dir.join("*.IMX")))
    expected_imxs = glob(str(expected_output_dir.join("*.IMX")))

    # 5. Compare actual output IMXs to expected output IMXs
    assert len(actual_imxs) == len(expected_imxs)
    for actualimx, expectedimx in zip(sorted(actual_imxs), sorted(expected_imxs)):
        assert os.path.basename(actualimx) == os.path.basename(expectedimx)
        assert imx_images_identical(actualimx, expectedimx)
