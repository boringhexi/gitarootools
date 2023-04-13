# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
from io import SEEK_CUR

from gitarootools.miscutils.datautils import open_maybe, readstruct


def animnames_from_gmo(file_or_path) -> list[str]:
    """return all animation names from a GMO model file

    :param file_or_path: file path or already-open GMO file
    :return: list of string animation names
    """
    with open_maybe(file_or_path, "rb") as file:
        magic = file.read(0x10)
        if magic != b"OMG.00.1PSP\0\0\0\0\0":
            raise ValueError("Not a valid GMO file")

        animnames = []
        while True:
            try:
                chunktype, headersize, chunksize = readstruct(file, "<HHI")
                if chunktype in (0x0002, 0x0003):  # outer chunk
                    # skip rest of this chunk header
                    file.seek(headersize - 8, SEEK_CUR)
                elif chunktype == 0x000B:  # animation
                    # seek to offset 0x10 of chunk header
                    file.seek(8, SEEK_CUR)
                    animname_bytes = file.read(headersize - 0x10)
                    animname = animname_bytes.split(b"\0", maxsplit=1)[0].decode(
                        encoding="utf8"
                    )
                    animnames.append(animname)
                else:  # all other chunks
                    # skip rest of this chunk
                    file.seek(chunksize - 8, SEEK_CUR)

            except EOFError:
                break
    return animnames


def write_animnames(animnames: list[str], txtpath: str) -> None:
    """save a list of animation names to a text file

    :param animnames: list of string animation names
    :param txtpath: path to a text file to be written
    """
    with open(txtpath, "wt") as txtfile:
        txtfile.writelines("\r\n".join(animnames))
