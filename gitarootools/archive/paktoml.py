# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""paktoml.py - read/write toml representations of PAK container files

This module can take a PakContainer instance from pakcontainer.py, extract its
contents, and create a toml file that describes how to repack the contents into an
PAK container. It can also do the repacking, taking a toml file + contents and
loading them into an PakContainer instance.

A toml file is a plaintext file of human-readable values.
"""
import os
from typing import AnyStr, Callable

import tomlkit

from gitarootools.archive.pakcontainer import PakContainer, PakModelItem

_toml_header = """\
# This is a list of all images and models extracted from the PAK container.
# Use gm-pakpack to repack everything back into an PAK file.
# Try opening this file in a programmer's text editor for handy color highlighting
# (your editor may need a plugin for TOML support first).

["Help/Guide"]
    # A [[ModelItem]] is a .gmo model.

    file-path = "MODEL.gmo"
    # file-path: filename of the GMO model.
    # Or can be a file path to a model in a different directory, e.g. models/MODEL.gmo

"""


def read_pak_from_toml(tomlpath: AnyStr) -> PakContainer:
    pass
    """read a PakContainer from a toml file and its content files

    :param tomlpath: path to the toml file
    :return: PakContainer instance read from tomlpath
    """
    tomldir = os.path.dirname(tomlpath)
    with open(tomlpath, "rt", encoding="utf-8") as tomlfile:
        tomldoc = tomlkit.parse(tomlfile.read())

    if not ("ModelItem" in tomldoc):
        return PakContainer([])

    modelitems = []
    for tomlmodel in tomldoc["ModelItem"]:
        filepath = tomlmodel.get("file-path")
        with open(os.path.join(tomldir, filepath), "rb") as itemfile:
            filedata = itemfile.read()
        filename = os.path.basename(filepath)
        modelitems.append(PakModelItem(filename, filedata))

    return PakContainer(modelitems)


def write_pak_to_toml(
    pak: PakContainer,
    output_dirpath: str,
    output_tomlbase: str,
    progressfunc: Callable = None,
) -> None:
    """write PakContainer to a plaintext toml file and extracted contents

    :param pak: PakContainer instance
    :param output_dirpath: new directory to create and to unpack PAK contents to
    :param output_tomlbase: base filename to which to write the .PAK.toml file (will be
        put in output_dirpath)
    :param progressfunc: function to run whenever an item of the PakContainer is about
      to be processed. It must accept three arguments: an int item index, an int total
      number of items, and a PakItem instance
    """
    # prepare toml dir and toml file. writing a bit early here, but if dir/file can't be
    # written, it's better to error before the time-consuming part instead of after
    tomldir = output_dirpath
    tomlpath = os.path.join(tomldir, output_tomlbase)
    os.makedirs(tomldir, exist_ok=True)

    num_modelitems = len(pak.modelitems)
    with open(tomlpath, "wt", encoding="utf-8") as tomlfile:
        try:
            tomldoc = tomlkit.parse(_toml_header)

            tomldoc.add("ModelItem", tomlkit.aot())
            for idx, modelitem in enumerate(pak.modelitems):
                if progressfunc is not None:
                    progressfunc(idx, num_modelitems, modelitem)

                # Save model item to file
                modelitem_outname = modelitem.name.replace(
                    os.path.sep, "_"
                )  # sanitize output filename, just in case
                with open(os.path.join(tomldir, modelitem_outname), "wb") as itemfile:
                    itemfile.write(modelitem.filedata)

                # Gather & add this pak item's info to toml document
                tomlmodel = tomlkit.table()
                tomlmodel["file-path"] = modelitem_outname
                tomldoc["ModelItem"].append(tomlmodel)

            tomlfile.write(tomldoc.as_string())

        except Exception:
            # noinspection PyBroadException
            try:
                # For debug output, try to write current tomldoc + error traceback
                import traceback

                tb = traceback.format_exc()
                tomlfile.write(tomldoc.as_string())
                tomlfile.write("\n\n# == ERROR ENCOUNTERED DURING WRITING ==\n#")
                tomlfile.write("\n#".join(tb.split("\n")))
            except Exception:
                pass
            raise
