# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""xgmtoml.py - read/write toml representations of XGM container files

This module can take an XgmContainer instance from xgmcontainer.py, extract its
contents, and create a toml file that describes how to repack the contents into an
XGM container. It can also do the repacking, taking a toml file + contents and
loading them into an XgmContainer instance.

A toml file is a plaintext file of human-readable values.
"""
import os
from typing import AnyStr, Callable

import tomlkit

from gitarootools.archive.xgmcontainer import XgmContainer
from gitarootools.archive.xgmitem import XgmImageItem, XgmModelItem
from gitarootools.miscutils.extutils import ANIMSEP_EXT, replaceext


class XgmTomlError(Exception):
    """base class for XGM TOML errors"""

    pass


# TODO expand help text
_toml_header = """\
# Welcome to the gm-xgmpack repacking file, for all your XGM repacking needs!
# Try opening this file in a programmer's text editor for handy color highlighting
# (your editor may need a plugin for TOML support first).

["Item Help/Guide"]
    # An ImageItem contains just an .IMX image file.
    # A ModelItem contains both .XG model and .animsep (animation separation) files.

    name16 = "MODEL.XG"
    # name16: Unless you use an advanced option below, this is the IMX or XG/animsep
    # files to use. Also used internally by the game, so it must be 16 ascii characters
    # or fewer.

    # Advanced options: fine control over the file(s) to use.
    # By default, name16="MODEL.XG" will use MODEL.XG and MODEL.animsep.
    # Use the following if the real filename is different or is in another directory.

    file-path = "models/filename.xg"
    # file-path: path to the actual XG or IMX file, if it's different from <name16>.
    # Also, animsep path will be based on this instead unless you use the option below.

    animsep-path = "elsewhere/another_file.animsep"
    # (ModelItem-only) animsep-path: path to the animation separation file, if
    # automatically basing it on <name16> or <file-path> isn't enough.

"""


def read_toml(tomlpath: AnyStr) -> XgmContainer:
    """read an XgmContainer from a toml file and its content files

    :param tomlpath: path to the toml file
    :return: XgmContainer instance read from tomlpath
    """
    tomldir = os.path.dirname(tomlpath)
    with open(tomlpath, "rt", encoding="utf-8") as tomlfile:
        tomldoc = tomlkit.parse(tomlfile.read())

    if not ("ImageItem" in tomldoc or "ModelItem" in tomldoc):
        return XgmContainer([], [])

    imageitems = []
    for tomlimage in tomldoc["ImageItem"]:
        # 1. read ImageItem info from TOML
        name16 = tomlimage["name16"]
        filepath = tomlimage.get("file-path")
        if filepath is None:
            filepath = name16
        # 2. read file data
        with open(os.path.join(tomldir, filepath), "rb") as itemfile:
            filedata = itemfile.read()
        # 3. Convert to XgmImageItem
        imageitems.append(XgmImageItem(name16, filedata))

    modelitems = []
    for tomlmodel in tomldoc["ModelItem"]:
        # 1. read ImageItem info from TOML
        name16 = tomlmodel["name16"]
        filepath = tomlmodel.get("file-path")
        if filepath is None:
            filepath = name16
        animseppath = tomlmodel.get("animsep-path")
        if animseppath is None:
            animseppath = replaceext(filepath, ANIMSEP_EXT)
        # 2. read file data
        with open(os.path.join(tomldir, filepath), "rb") as itemfile:
            filedata = itemfile.read()
        with open(os.path.join(tomldir, animseppath), "rb") as animsepfile:
            animsepdata = animsepfile.read()
        # 3. Convert to XgmModelItem
        modelitems.append(XgmModelItem(name16, filedata, animsepdata))

    return XgmContainer(imageitems, modelitems)


def write_toml(
    xgm: XgmContainer,
    output_dirpath: str,
    output_tomlbase: str,
    progressfunc: Callable = None,
) -> None:
    """write an XgmContainer to a plaintext toml file and extracted contents

    :param xgm: XgmContainer instance
    :param output_dirpath: new directory to create and to unpack XGM contents to
    :param output_tomlbase: base filename to which to write the .XGM.toml file (will be
        put in output_dirpath)
    :param progressfunc: function to run whenever an item of the XgmContainer is about
      to be processed. It must accept three arguments: an int item index, an int total
      number of items, and an xgmitem.XgmImageItem/XgmModelItem instance
    """

    # prepare toml dir and toml file. writing a bit early here, but if dir/file can't be
    # written, it's better to error before the time-consuming part instead of after
    tomldir = output_dirpath
    tomlpath = os.path.join(tomldir, output_tomlbase)
    os.makedirs(tomldir, exist_ok=True)

    num_imageitems, num_modelitems = len(xgm.imageitems), len(xgm.modelitems)
    with open(tomlpath, "wt", encoding="utf-8") as tomlfile:
        try:
            tomldoc = tomlkit.parse(_toml_header)

            tomldoc.add("ImageItem", tomlkit.aot())
            for idx, imageitem in enumerate(xgm.imageitems):
                if progressfunc is not None:
                    progressfunc(idx, num_imageitems, imageitem)

                # Extract image item to file
                imageitem_outname = imageitem.name16.replace(
                    os.path.sep, "_"
                )  # sanitize
                with open(os.path.join(tomldir, imageitem_outname), "wb") as itemfile:
                    itemfile.write(imageitem.filedata)

                # Gather & add this image item's info to toml document
                tomlimage = tomlkit.table()
                tomlimage["name16"] = imageitem.name16
                if imageitem_outname != imageitem.name16:
                    tomlimage["file-path"] = imageitem_outname
                # noinspection PyArgumentList
                tomldoc["ImageItem"].append(tomlimage)

            if xgm.modelitems:
                tomldoc.add(tomlkit.nl())
            tomldoc.add("ModelItem", tomlkit.aot())
            for idx, modelitem in enumerate(xgm.modelitems):
                if progressfunc is not None:
                    progressfunc(idx, num_modelitems, modelitem)

                # Extract model item to file
                modelitem_outname = modelitem.name16.replace(
                    os.path.sep, "_"
                )  # sanitize
                with open(os.path.join(tomldir, modelitem_outname), "wb") as itemfile:
                    itemfile.write(modelitem.filedata)
                # Extract animation entry data to file
                animsep_outname = replaceext(modelitem_outname, ANIMSEP_EXT)
                with open(os.path.join(tomldir, animsep_outname), "wb") as animsepfile:
                    animsepfile.write(modelitem.animdata)

                # Gather & add this model item's info to toml document
                tomlmodel = tomlkit.table()
                tomlmodel["name16"] = modelitem.name16
                if modelitem_outname != modelitem.name16:
                    tomlimage["file-path"] = modelitem_outname
                # noinspection PyArgumentList
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
