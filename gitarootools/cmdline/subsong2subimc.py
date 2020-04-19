#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""subsong2subimc.py - command-line tool to convert subsongs to .sub.imc format"""

import sys

from gitarootools.cmdline.subsong2common import run_script


def main(args=tuple(sys.argv[1:])):
    """args: sequence of command line argument strings"""
    run_script("subimc", args)


if __name__ == "__main__":
    main()
