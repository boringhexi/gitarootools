#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imccontainer.py - read/write IMC audio container files

An IMC audio container file is a file type from Gitaroo Man that has the extension .IMC
and contains audio subsongs."""

import struct
from itertools import zip_longest, count

from gitarootools.audio import subsong
from gitarootools.miscutils.datautils import chunks, open_maybe, readstruct

# subsong memory load modes, maps strings to raw values
loadmodes_toraw = {
    "stream": 0,  # load part at a time, e.g. music
    "entire": 2,  # load entire subsong and keep it in mem, e.g. sfx
}
# same, but maps raw values to strings
loadmodes_fromraw = {rawval: string for string, rawval in loadmodes_toraw.items()}


class ImcContainerError(Exception):
    """base class for IMC container related errors"""

    pass


class ContainerSubsong:
    """transparent wrapper around a subsong.Subsong instance, containing additional info
    needed to put it into an ImcContainer

    all of the Subsong instance's public attributes are exposed by the ContainerSubsong
    instance; they can be transparently accessed and assigned to.
    """

    def __init__(self, subsong_, name, loadmode, rawname=None, unk1=None, unk2=None):
        """

        subsong_: a subsong.Subsong instance to wrap
        name: 16 ascii characters or fewer
        loadmode: 'stream' (e.g. music) or 'entire' (load all at once e.g. sfx)

        arguments below are optional, should come from the original IMC container
        file to reduce the size of the resulting binary diff patch:
          rawname: (optional) original 16-byte name including null byte + garbage
          unk1, unk2: (optional) original 32-bit unsigned values with unknown purpose
        """
        self._subsong = subsong_
        self.name = name
        self.loadmode = loadmode
        self.rawname = rawname
        self.unk1, self.unk2 = unk1, unk2

    def __dir__(self):
        """return own contents + self._subsong's public contents"""
        dir_contents = set()
        subsong_contents = filter(
            lambda x: not x.startswith("__"), self._subsong.__dir__()
        )
        dir_contents.update(super().__dir__(), subsong_contents)
        return dir_contents

    def __getattr__(self, name):
        """if name isn't found in self, also check self._subsong's public contents"""
        return getattr(self._subsong, name)

    def __setattr__(self, name, value):
        """if name exists in self._subsong's public contents, assign to it instead"""
        if name == "_subsong":
            object.__setattr__(self, "_subsong", value)
        elif not name.startswith("__") and hasattr(self._subsong, name):
            setattr(self._subsong, name, value)
        else:
            object.__setattr__(self, name, value)

    @property
    def name(self):
        """16 ascii characters or fewer"""
        return self._name

    @name.setter
    def name(self, value):
        try:
            value.encode(encoding="ascii")
        except UnicodeError as e:
            if hasattr(e, "start") and hasattr(e, "end"):
                nonascii = value[e.start : e.end]
                raise ValueError(f"name {value!r} contains non-ascii {nonascii!r}")
            else:
                raise ValueError(f"name {value!r} contains non-ascii")
        if len(value) > 16:
            raise ValueError("name must be 16 or fewer ascii characters")
        self._name = value

    @property
    def loadmode(self):
        """determines this subsong's load mode: either stream in parts or load entirely

        This property can be assigned the strings "stream" or "entire" or their
        corresponding raw values 0 or 2. Accessing this property will always return
        the string version; for the raw value, use loadmode_raw.
        """
        return self._loadmode

    @loadmode.setter
    def loadmode(self, value):
        if value in loadmodes_toraw:
            self._loadmode = value
        elif value in loadmodes_fromraw:
            self._loadmode = loadmodes_fromraw[value]
        else:
            raise ValueError(
                f"loadmode can only be assigned strings {tuple(loadmodes_toraw.keys())}"
                f" or their corresponding ints {tuple(loadmodes_toraw.values())}"
            )

    @property
    def loadmode_raw(self):
        """raw value that corresponds to the current loadmode"""
        return loadmodes_toraw[self.loadmode]

    @property
    def rawname(self):
        """bytes of length 16, or can be None"""
        return self._rawname

    @rawname.setter
    def rawname(self, value):
        if value is not None and len(value) != 16:
            raise ValueError(
                f"rawname must be length 16, was {value!r} with length {len(value)}"
            )
        self._rawname = value

    def get_imcdata(self):
        """interleaves and returns subsong's PS-ADPCM data, including header

        (It's Subsong.get_imcdata but uses self.loadmode instead of `entire` arg)

        PS-ADPCM data is returned with a certain number of frames per block (fpb) and
        blocks per channel (bpc). There are 3 possibilities, in this order of priority:
        - use self.original_block_layout's saved fpb/bpc if it has them
        - if self.loadmode=="entire",  use large fpb + just enough bpc to hold the data
        - otherwise (loadmode=="stream"), use 768 fpb + just enough bpc to hold the data
        "entire" is for sound effects but not music, "otherwise" is for both (sfx/music)
        """
        entire = self.loadmode == "entire"
        return self._subsong.get_imcdata(entire=entire)

    def clear_patchfinfo(self):
        """clear patch-friendly info: rawname, unk1/unk2, original block layout

        clear (i.e. set to None) info that would otherwise be used to restore the
        original layout from a Gitaroo Man subsong
        """
        self.rawname = None
        self.unk1 = self.unk2 = None
        self._subsong.original_block_layout = None


class ImcContainer:
    def __init__(self, containersubsongs):
        """initialize an ImcContainer
        containersubsongs: iterable of imccontainer.ContainerSubsong instances"""
        self.csubsongs = list(containersubsongs)

    @property
    def num_subsongs(self):
        return len(self.csubsongs)


def read_imc(file):
    """ read from a IMC audio container file and return an ImcContainer

    file: A file path. Or it can be an already-opened file, in which case:
    - it will read starting from the current file position, with no guarantee of file
      position after returning
    - the caller is responsible for closing the file afterwards
    raises: EOFError if end of file is reached unexpectedly
    """
    with open_maybe(file, "rb") as file:
        start_offset = file.tell()

        # read number of subsongs
        num_subsongs = readstruct("<I", file)

        # read raw ssinfo
        fmt, items_per_ssinfo_entry = ("<" + "16s4I" * num_subsongs), 5
        raw_ssinfos = tuple(chunks(readstruct(fmt, file), items_per_ssinfo_entry))
        next_ssoffsets = (x[1] for x in raw_ssinfos[1:])

        # read subsongs, convert to ContainerSubsongs
        csubsongs = []
        for raw_ssinfo, next_ssoffset in zip_longest(
            raw_ssinfos, next_ssoffsets, fillvalue=None
        ):
            rawname, ssoffset, unk1, unk2, loadmode_raw = raw_ssinfo
            name = rawname.split(b"\0", 1)[0].decode(encoding="ascii")

            if next_ssoffset is not None:
                ss_knownsize = next_ssoffset - ssoffset
            else:
                ss_knownsize = None

            # read Subsong from within IMC container file
            file.seek(start_offset + ssoffset)
            subsong_ = subsong.read_subimc(file, knownsize=ss_knownsize)
            csubsong = ContainerSubsong(
                subsong_, name, loadmode_raw, rawname, unk1, unk2
            )
            csubsongs.append(csubsong)

        return ImcContainer(csubsongs)


def write_imc(imccontainer, file, progressfunc=None):
    """write an ImcContainer to an IMC audio container file

    imccontainer: an ImcContainer object
    file: A file path. Or it can be an already-opened file, in which case:
    - it will write starting from the current file position, with no guarantee of file
      position after returning
    - the caller is responsible for closing the file afterwards
    progressfunc: function to run whenever a subsong of the ImcContainer is about to
      be processed. It must accept three arguments: an int subsong index, an int total
      number of subsongs, and an imccontainer.ContainerSubsong instance
    """
    with open_maybe(file, "wb") as file:
        start_offset = file.tell()  # in case we're reading from inside an ISO file, etc

        # write num_subsongs
        num_subsongs = imccontainer.num_subsongs
        file.write(struct.pack("<I", num_subsongs))
        if not num_subsongs:
            return

        # true offsets for subsong info entries (contained in the IMC container header)
        true_ssinfoentry_offsets = (
            start_offset + 4 + i * 0x20 for i in range(num_subsongs)
        )
        file.seek(start_offset + 4 + num_subsongs * 0x20)  # after the last ssinfo entry

        for ssidx, true_ssinfoentry_offset, csubsong in zip(
            count(), true_ssinfoentry_offsets, imccontainer.csubsongs
        ):
            if progressfunc is not None:
                progressfunc(ssidx, imccontainer.num_subsongs, csubsong)

            # current pos is where we should write the subsong, but we won't just yet
            true_subsong_offset = file.tell()
            subsong_offset = true_subsong_offset - start_offset

            # prepare subsong info entry
            # uses patch-friendly info if present: rawname, unk1, unk2
            if csubsong.rawname is not None:
                # use csubsong.name pasted on top of csubsong.rawname
                rawname = csubsong.name.encode(encoding="ascii")
                if len(rawname) < 16:
                    rawname += b"\0"
                    rawname += csubsong.rawname[len(rawname) :]
            else:
                # just zero-pad csubsong.name
                rawname = csubsong.name.encode(encoding="ascii")
                rawname += (16 - len(rawname)) * b"\0"
            unk1 = 0 if csubsong.unk1 is None else csubsong.unk1
            unk2 = 0 if csubsong.unk2 is None else csubsong.unk2
            ss_infoentry = struct.pack(
                "<16s4I", rawname, subsong_offset, unk1, unk2, csubsong.loadmode_raw
            )

            # write subsong info entry into IMC container header
            file.seek(true_ssinfoentry_offset)
            file.write(ss_infoentry)

            # write subsong data
            file.seek(true_subsong_offset)
            subsong.write_subimc(csubsong, file)
