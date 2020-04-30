# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""xgmcontainer.py - read/write XGM container files

An XGM container file is a file type from Gitaroo Man that has the extension .XGM
and contains image files, models files, and additional animation data."""

import struct
from typing import AnyStr, BinaryIO, Callable, Sequence, Union

from gitarootools.miscutils.datautils import open_maybe, readstruct

from .xgmitem import (
    XgmImageItem,
    XgmModelItem,
    read_imageitem,
    read_modelitem,
    write_imageitem,
    write_modelitem,
)


class XgmContainerError(Exception):
    """base class for IMC container related errors"""

    pass


class XgmContainer:
    def __init__(
        self, imageitems: Sequence[XgmImageItem], modelitems: Sequence[XgmModelItem]
    ):
        """Initialize an XGM container

        :param imageitems: sequence of xgmitem.XgmImageItem
        :param modelitems: sequence of xgmitem.XgmModelItem
        """
        self.imageitems = imageitems
        self.modelitems = modelitems


def read_xgm(file: Union[AnyStr, BinaryIO]) -> XgmContainer:
    """read from file and return an XgmContainer

    :param file: A file path. Or it can be an already-opened file, in which case:
        * data will be read starting from the current file position
        * after returning, file position is at the end of the last item's data
        * the caller is responsible for closing the file afterwards
    :return: XgmContainer instance
    """
    with open_maybe(file, "rb") as file:
        num_imageitems, num_modelitems = readstruct(file, "<II")
        imageitems = [read_imageitem(file) for _ in range(num_imageitems)]
        modelitems = [read_modelitem(file) for _ in range(num_modelitems)]
    return XgmContainer(imageitems, modelitems)


def write_xgm(
    xgm: XgmContainer, file: Union[AnyStr, BinaryIO], progressfunc: Callable = None
) -> None:
    """write an XgmContainer to file

    :param xgm: XgmContainer object
    :param file: A file path. Or it can be an already-opened file, in which case:
        * data will be written starting from the current file position
        * after returning, file position is at the end of the last item's data
        * the caller is responsible for closing the file afterwards
    :param progressfunc: function to run whenever an item of the XgmContainer is about
      to be processed. It must accept three arguments: an int item index, an int total
      number of items, and an xgmitem.XgmImageItem/XgmModelItem instance
    """
    with open_maybe(file, "wb") as file:
        num_imageitems, num_modelitems = len(xgm.imageitems), len(xgm.modelitems)
        file.write(struct.pack("<II", num_imageitems, num_modelitems))
        for i, item in enumerate(xgm.imageitems):
            if progressfunc is not None:
                progressfunc(i, num_imageitems, item)
            write_imageitem(item, file)
        for item in xgm.modelitems:
            if progressfunc is not None:
                progressfunc(i, num_modelitems, item)
            write_modelitem(item, file)
