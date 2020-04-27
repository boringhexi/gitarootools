# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""xgmitem.py - read/write the contents of an XGM container"""
import struct
from typing import BinaryIO

# data of a single blank animation entry, used by models without animations
BLANK_ANIMDATA = struct.pack("<3f20x", 2, 1, 60)


class XgmItemError(Exception):
    """base class for XGM item-related exceptions"""

    pass


class EndOfXgmItemError(XgmItemError, EOFError):
    """raised when the end of an XGM item is reached unexpectedly"""

    pass


class XgmImageItem:
    def __init__(self, name16: str, filedata: bytes) -> None:
        """initialize a XGM image item

        :param name16: ascii filename, max length 16
        :param filedata: file contents
        """
        self.name16 = name16
        self._filedata = filedata

    @property
    def name16(self) -> str:
        """ascii filename, max length 16"""
        return self._name

    @name16.setter
    def name16(self, val: str):
        if not len(val) <= 16:
            raise ValueError("name16 must be 16 ascii characters or less")
        try:
            val.encode("ascii")
        except UnicodeDecodeError:
            raise ValueError("name16 must be 16 ascii characters or less")
        self._name = val

    @property
    def filedata(self) -> bytes:
        """file contents"""
        return self._filedata

    @property
    def filesize(self) -> int:
        """size of file data in bytes"""
        return len(self.filedata)


class XgmModelItem:
    def __init__(self, name16: str, filedata: bytes, animdata: bytes = None) -> None:
        """initialize a XGM model item

        :param name16: ascii filename, max length 16, will be converted to uppercase
        :param filedata: file contents
        :param animdata: contents of model animation entries. if None, a single
            blank entry will be added automatically
        """
        self.name16 = name16
        self._filedata = filedata
        if animdata is not None:
            self._animdata = animdata
        else:
            self._animdata = BLANK_ANIMDATA

    @property
    def name16(self) -> str:
        """ascii filename, max length 16"""
        return self._name

    @name16.setter
    def name16(self, val: str):
        if not len(val) <= 16:
            raise ValueError("name16 must be 16 ascii characters or less")
        try:
            val.encode("ascii")
        except UnicodeDecodeError:
            raise ValueError("name16 must be 16 ascii characters or less")
        self._name = val

    @property
    def filedata(self) -> bytes:
        """file contents"""
        return self._filedata

    @property
    def filesize(self) -> int:
        """size of file data in bytes"""
        return len(self._filedata)

    @property
    def animdata(self) -> bytes:
        """data for animation entries"""
        return self._animdata

    @property
    def num_animentries(self) -> int:
        """number of animation entries"""
        return len(self._animdata) // 0x20


def read_imageitem(file):
    """read from file and return a XgmImageItem

    file: An already-opened file object containing this item's data.
    - the item will be read starting from the current file position
    - after returning, file position is at the end of the item data
    - the caller is responsible for closing the file afterwards
    raises:
    - EndOfXgmItemError if end of item is reached unexpectedly
    """
    header = file.read(0x130)
    if len(header) != 0x130:
        raise EndOfXgmItemError(
            "Expected 0x130 bytes for XGM image item's header, only got"
            f"{len(header):#x} bytes"
        )
    rawname, filesize = struct.unpack("<256x16s4xI24x", header)
    name16 = rawname.split(b"\0", 1)[0].decode(encoding="ascii")
    filedata = file.read(filesize)
    if len(filedata) != filesize:
        raise EndOfXgmItemError(
            f"Expected {filesize} bytes for XGM image item contents, but only"
            f"{len(filedata)} bytes remain in file"
        )
    return XgmImageItem(name16, filedata)


def read_modelitem(file):
    """read from file and return a XgmModelItem

    file: An already-opened file object containing this item's data.
    - the item will be read starting from the current file position
    - after returning, file position is at the end of the item data
    - the caller is responsible for closing the file afterwards
    raises:
    - EndOfXgmItemError if end of item is reached unexpectedly
    """
    header = file.read(0x120)
    if len(header) != 0x120:
        raise EndOfXgmItemError(
            "Expected 0x120 bytes for XGM image item's header, only got"
            f"{len(header):#x} bytes"
        )
    rawname, filesize, num_anims = struct.unpack("<256x16s4xII4x", header)
    name16 = rawname.split(b"\0", 1)[0].decode(encoding="ascii")
    animsepsize = num_anims * 0x20
    animentries = file.read(animsepsize)
    if len(animentries) != animsepsize:
        raise EndOfXgmItemError(
            f"Expected {animsepsize} bytes for XGM model animation entries, but only"
            f"{len(animentries)} bytes remain in file"
        )
    filedata = file.read(filesize)
    if len(filedata) != filesize:
        raise EndOfXgmItemError(
            f"Expected {filesize} bytes for XGM model item contents, but only"
            f"{len(filedata)} bytes remain in file"
        )
    return XgmModelItem(name16, filedata, animdata=animentries)


def write_imageitem(imageitem: XgmImageItem, file: BinaryIO):
    """write a XGM image item to file

    :param imageitem: XgmImageItem object to be written
    :param file: already-opened file in binary write mode.
        * data will be written starting from the current file position
        * after returning, file position is at the end of the written data
        * the caller is responsible for closing the file afterwards
    """
    headerdata = struct.pack(
        "<256x16s4xI24x", imageitem.name16.encode("ascii"), imageitem.filesize
    )
    file.write(headerdata)
    file.write(imageitem.filedata)


def write_modelitem(modelitem: XgmModelItem, file: BinaryIO):
    """write a XGM model item to file

    :param modelitem: XgmModelItem object to be written
    :param file: already-opened file in binary write mode.
        * data will be written starting from the current file position
        * after returning, file position is at the end of the written data
        * the caller is responsible for closing the file afterwards
    """
    headerdata = struct.pack(
        "<256x16s4xII4x",
        modelitem.name16.encode("ascii"),
        modelitem.filesize,
        modelitem.num_animentries,
    )
    file.write(headerdata)
    file.write(modelitem.animdata)
    file.write(modelitem.filedata)
