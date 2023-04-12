# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""pakcontainer.py - read/write PAK container files

A PAK container file is a file type from Gitaroo Man Lives! that has the extension .PAK
and contains model files. It's a list of file sizes followed by concatenated files.
"""
from io import SEEK_CUR, SEEK_END
from typing import AnyStr, BinaryIO, Callable, Iterable, Optional, Sequence, Union

from gitarootools.miscutils.datautils import (
    open_maybe,
    readdata,
    readstruct,
    writestruct,
)
from gitarootools.miscutils.extutils import replaceext


class PakModelItem:
    def __init__(self, name: str, filedata: bytes) -> None:
        """initialize a PAK model item

        :param name: ascii filename, max length 16
        :param filedata: file contents
        """
        self.name = name
        self._filedata = filedata

    @property
    def filedata(self) -> bytes:
        """file contents"""
        return self._filedata

    @property
    def filesize(self) -> int:
        """size of file data in bytes"""
        return len(self.filedata)


class PakContainer:
    def __init__(self, modelitems: Iterable[PakModelItem]) -> None:
        """Initialize a PAK container

        :param modelitems: sequence of PakModelItem
        """
        self.modelitems = list(modelitems)


def read_pak(
    pakfile: Union[AnyStr, BinaryIO],
    pakfilesize: Optional[int] = None,
    ssqfile: Union[None, AnyStr, BinaryIO] = None,
) -> PakContainer:
    """read from file and return a PakContainer

    :param pakfile: A PAK file path. Or it can be an already-opened file, in which case:
        - data will be read starting from the current file position
        - after returning, file position is at the end of the last item's data
        - the caller is responsible for closing the file afterwards
    :param pakfilesize: Usually the pakfile's size will be determined by seeking
        to the end of the file. If this is not feasible (e.g. pakfile is contained
        within a larger file), use this to pass the pakfile's true size.
    :param ssqfile: An optional SSQ file path (or already-opened file, following the
        same rules as pakfile) from which to pull a list of filenames to name the PAK
        container's files. Without this, the files will be named in increasing numeric
        order instead.
    :return: PakContainer instance
    """

    with open_maybe(pakfile, "rb") as pakfile:
        if ssqfile is not None:
            with open_maybe(ssqfile, "rb") as ssqfile:
                itemnames = read_ssq_itemnames_gmo(ssqfile)
            itemsizes = readstruct(pakfile, f"<{len(itemnames)}I")

        else:
            # get total size of PAK file
            if pakfilesize is None:
                start_position = pakfile.tell()
                end_position = pakfile.seek(0, SEEK_END)
                pakfilesize = end_position - start_position
                pakfile.seek(start_position)

            # Get list of uint32 item sizes:
            # Read a uint32 from the beginning, compare to remaining pakfile size,
            # repeat until sum of uint32s would be greater (i.e. one too many)
            itemsizes = []
            sum_itemsizes = 0
            remaining_paksize = pakfilesize
            while True:
                itemsize = readstruct(pakfile, "<I")
                remaining_paksize -= 4
                if sum_itemsizes + itemsize <= remaining_paksize:
                    sum_itemsizes += itemsize
                    itemsizes.append(itemsize)
                else:
                    pakfile.seek(-4, SEEK_CUR)
                    break

            digits = len(str(len(itemsizes)))
            itemnames = [f"{x:0{digits}}.gmo" for x in range(len(itemsizes))]

        # Now we have a list of item names and sizes, and the pakfile seek position is
        # at the beginning of the first item's data.
        itemdatas = [readdata(pakfile, x) for x in itemsizes]

    return PakContainer(
        PakModelItem(filename, filedata)
        for filename, filedata in zip(itemnames, itemdatas)
    )


def read_ssq_itemnames_gmo(file: BinaryIO) -> Sequence[str]:
    """get .gmo filenames from an SSQ file

    :param file: already-open SSQ file, with the current position at the beginning of
        the SSQ file
    :return: sequence of XG filenames corresponding to this SSQ's PAK container
    contents, but with all the file .XG file extensions replaced with .gmo
    """
    file.seek(0x28, SEEK_CUR)
    num_imx_entries = readstruct(file, "<I")
    file.seek(0x20 * num_imx_entries, SEEK_CUR)
    num_xg_entries = readstruct(file, "<I")
    itemnames = []
    for i in range(num_xg_entries):
        xg_name_bytes = file.read(0x10)
        xg_name = xg_name_bytes.split(b"\x00", maxsplit=1)[0].decode(
            encoding="ascii", errors="replace"
        )
        is_clone = readstruct(file, "<I")
        if not is_clone:
            xg_name = replaceext(xg_name, ".gmo", ".XG")
            itemnames.append(xg_name)
        file.seek(0x1c, SEEK_CUR)
    return itemnames


def write_pak(
    pak: PakContainer, file: Union[AnyStr, BinaryIO], progressfunc: Callable = None
) -> None:
    """write a PakContainer to file

    :param pak: PakContainer object
    :param file: A file path. Or it can be an already-opened file, in which case:
        * data will be written starting from the current file position
        * after returning, file position is at the end of the last item's data
        * the caller is responsible for closing the file afterwards
    :param progressfunc: function to run whenever an item of the PakContainer is about
      to be processed. It must accept three arguments: an int item index, an int total
      number of items, and a PakModelItem instance
    """
    with open_maybe(file, "wb") as file:
        for item in pak.modelitems:
            writestruct(file, "<I", item.filesize)
        num_modelitems = len(pak.modelitems)
        for i, item in enumerate(pak.modelitems):
            if progressfunc is not None:
                progressfunc(i, num_modelitems, item)
            file.write(item.filedata)
