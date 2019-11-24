#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imctoml.py - read/write toml representations of IMC audio container files

This module can take an ImcContainer instance from imccontainer.py, extract its
subsongs, and create a toml file that describes how to repack those subsongs into an
IMC container. It can also do the repacking, taking a toml file + subsong files and
loading them into an ImcContainer instance.

A toml file is a plaintext file of human-readable values.
"""
import os
import warnings

import tomlkit

from gitarootools.audio.imccontainer import ImcContainer, ContainerSubsong
from gitarootools.audio.subsong import read_subsong
from gitarootools.miscutils.extutils import IMCTOML_EXT, SUBSONG_FORMATS

SUBIMC_EXT = SUBSONG_FORMATS["subimc"]


class ImcTomlWarning(UserWarning):
    """base class for IMC TOML warnings"""

    pass


class MaxSizeWarning(ImcTomlWarning):
    """warning when a rebuilt IMC file exceeds/will exceed the maximum specified size"""

    pass


class ChannelAlreadyReplacedWarning(ImcTomlWarning):
    """warning when a channel that was already replaced is being replaced again"""

    pass


# TODO if a wiki page is created with more details, mention it in this help text
_toml_header = """\
# Welcome to the gm-imcpack repacking file, for all your IMC repacking needs!
# When you ran gm-imcunpack on an IMC audio container file from Gitaroo Man, it spat out
# a bunch of .sub.imc subsongs and this file.
# So, what now? You can make some changes, repack it into an IMC container, and
# reinsert it into the game. Typically you will:
#  1. Use gm-subsong2wav to convert some .sub.imc subsongs to WAV format.
#  2. Edit them to your liking in a program like Audacity.
#  3. Change some of the "basefile" entries below to point to the edited WAV files.
#  3b. Or instead, you can uncomment and use the "channels-#" entries to replace only
#      specific channels with those from the edited WAV files.
#      (See ["Subsong Help/Guide"] below to see when and why this is recommended.)
#  4. Run `gm-imcpack <this directory or this file>` to repack the IMC audio container.
#  5. There's no convenient way to reinsert this file, so for now you'll have to copy it
#     in a hex editor and paste it directly into the original spot of the Gitaroo Man
#     ISO file.
#  6. You can create a binary diff patch (such as xdelta) between the original game and
#     your modified version, then send the patch to someone else so they can patch it
#     onto their copy of the game.

["Subsong Help/Guide"]
    # This section doesn't do anything. It's just a guide to help you edit the real
    # Subsong entries below.
    name = "A_INT"
    # name: Used internally in Gitaroo Man. Must be 16 ascii characters or less.
    loadmode = "stream"
    # loadmode: Memory loading mode, either "stream" or "entire".
    # "stream" will load only part at a time as it plays, typically used for music.
    # "entire" will load the whole thing in advance, typically used for sound effects.
    basefile = "00.A_INT.sub.imc"
    # basefile: Audio file containing this subsong's audio.
    # Option 1: You can change this to point to another file (such as a WAV file).
    # Option 2: You can use this file as-is and override only specific channels with
    # another file's (see below). If you don't need to modify every channel, Option 2 is
    # recommended because when you recompress a channel, it adds recompression noise and
    # increases the size of the binary diff patch.
    channels-56 = "00.A_INT.wav"
    # channels-#: Use this file's # channels to override the basefile's # channels.
    # In this example, channels 5 and 6 of this WAV file will override channels 5 and 6
    # of the basefile above. (Note: channels are numbered starting from 1, not 0.)
    channels-12-to-56 = "00.A_INT.wav"
    # channels-#-to-#: An alternative to the above. In this example, channels 1 and 2 of
    # this file will override channels 5 and 6 of the basefile, in that order.
    # (Advanced usage: Use multiple "channels-#" or "channels-#-to-#" entries to get
    # channels from more than one input file.)
    [patch-friendly-info]
    # Everything in this section can be safely left alone. It was automatically filled
    # with data from the original game. When [Repack-Settings].patch-friendly = true,
    # this data is used to match the original game data, reducing binary patch size.

[Repack-Settings]
    # Settings used by gm-imcpack during the repacking process. Comment out an entry to
    # disable it. (These can also be overridden by passing the relevant arguments to
    # gm-imcrepack.)
    patch-friendly = true
    # patchfriendly: If this entry exists and is true, the repacked IMC container will
    # closely match the layout of original, resulting in a smaller binary diff patch.
    # (This uses the [patch-friendly-info] sections below, ignoring any missing sections
    # or info.)
    max-size = 'REPLACE ME'
    # max-size: If this entry exists, gm-imcpack will warn you if the repacked IMC
    # container exceeds this size (size of the original file). Good to know when you are
    # pasting the repacked IMC container directly into the Gitaroo Man ISO in a hex
    # editor.

"""


def read_toml(tomlpath):
    """read an ImcContainer from a toml file and its subsong files

    tomlpath: path to the toml file. Any subsong files referenced within must be
      contained in the same dir as tomlpath
    """
    tomldir = os.path.dirname(tomlpath)
    with open(tomlpath, "rt", encoding="utf-8") as tomlfile:
        tomldoc = tomlkit.parse(tomlfile.read())

    if "Repack-Settings" in tomldoc:
        patch_friendly = tomldoc["Repack-Settings"].get("patch-friendly", False)
        max_size = tomldoc["Repack-Settings"].get("max-size", None)
    else:
        patch_friendly = False
        max_size = None

    if "Subsong" not in tomldoc:
        return ImcContainer([])

    csubsongs = []
    for tomlsubsong in tomldoc["Subsong"]:

        # 1. read ContainerSubsong info from TOML
        ss_name = tomlsubsong["name"]
        ss_loadmode = tomlsubsong["loadmode"]
        ss_basefile = tomlsubsong["basefile"]

        # 2. read patch-friendly-info if desired & possible
        ss_rawname = ss_unk1 = ss_unk2 = ofpb = obpc = None
        if patch_friendly:
            tomlpatchfinfo = tomlsubsong.get("patch-friendly-info", None)
            if tomlpatchfinfo is not None:
                if "rawname" in tomlpatchfinfo:
                    ss_rawname = bytes(tomlpatchfinfo["rawname"])
                if "unk" in tomlpatchfinfo:
                    ss_unk1, ss_unk2 = tomlpatchfinfo["unk"]
                if "frames-per-block" in tomlpatchfinfo:
                    ofpb = tomlpatchfinfo["frames-per-block"]
                if "blocks-per-channel" in tomlpatchfinfo:
                    obpc = tomlpatchfinfo["blocks-per-channel"]

        # 3. read subsong from .wav or .sub.imc file
        subsongpath = os.path.join(tomldir, ss_basefile)
        subsong = read_subsong(subsongpath)

        # 4. restore subsong's original block layout from TOML if desired & possible
        # (only if patch-friendly==True and this info exists in the TOML)
        subsong.original_block_layout = (ofpb, obpc)

        # 5. process subsong channel replacement entries
        already_replaced_channels = dict()
        for key, value in tomlsubsong.items():
            if key.startswith("channels-"):
                chanrepl_filename = value
                chanrepl_raw = key[len("channels-") :]  # e.g. "56" or "12-to-56"
                if "-to-" in chanrepl_raw:
                    chanrepl_rawsrc, chanrepl_rawdest = chanrepl_raw.split(
                        "-to-", maxsplit=1
                    )
                else:
                    chanrepl_rawsrc, chanrepl_rawdest = chanrepl_raw, chanrepl_raw
                # check if entry is invalid
                if not (
                    set(chanrepl_rawsrc).issubset(set("123456789"))
                    and set(chanrepl_rawsrc).issubset(set("123456789"))
                ):
                    raise ValueError(
                        f"subsong {ss_name}: "
                        "Channel replacement key name needs to be in a format like "
                        "channels-56 or channels-12-to-56, "
                        f"not 'channels-{chanrepl_raw}'"
                    )
                # another check for invalid entry
                elif not len(chanrepl_rawsrc) == len(chanrepl_rawdest):
                    raise ValueError(
                        f"subsong {ss_name}: "
                        "Channel replacement key name in a format like "
                        "channels-12-to-56 needs equal amount of numbers on "
                        'either side of "-to-", '
                        "not 'channels-{chanrepl_raw}'"
                    )
                else:
                    # Carry out channel replacement
                    chanrepl_subsong = read_subsong(
                        os.path.join(tomldir, chanrepl_filename)
                    )
                    chanrepl_src = (int(x) for x in chanrepl_rawsrc)
                    chanrepl_dest = (int(x) for x in chanrepl_rawdest)
                    for ch_src, ch_dest in zip(chanrepl_src, chanrepl_dest):
                        if ch_dest in already_replaced_channels:
                            prev_filename, prev_src = already_replaced_channels[ch_dest]
                            warnings.warn(
                                f"subsong {ss_name}: "
                                f"{ss_basefile} channel {ch_dest} was already "
                                f"replaced by {prev_filename} channel {prev_src}, "
                                "is being replaced again by "
                                f"{chanrepl_filename} channel {ch_src}",
                                ChannelAlreadyReplacedWarning,
                            )
                        already_replaced_channels[ch_dest] = (chanrepl_filename, ch_src)
                        chidx_src = ch_src - 1
                        chidx_dest = ch_dest - 1
                        try:
                            subsong.channels[chidx_dest] = chanrepl_subsong.channels[
                                chidx_src
                            ]
                        except IndexError:
                            if chidx_src >= chanrepl_subsong.num_channels:
                                oob_kind = "replacement"
                                oob_name = chanrepl_filename
                                oob_numchannels = chanrepl_subsong.num_channels
                                oob_oobchannel = ch_src
                            else:
                                oob_kind = "basefile"
                                oob_name = ss_basefile
                                oob_numchannels = subsong.num_channels
                                oob_oobchannel = ch_dest
                            raise IndexError(
                                f"subsong {ss_name}: "
                                f"Channel replacement entry {key!r} out of bounds, "
                                f"{oob_kind} {oob_name!r} only contains "
                                f"{oob_numchannels} channels, not {oob_oobchannel}"
                            )

        # 6. convert to a ContainerSubsong (name, loadmode, etc)
        csubsong = ContainerSubsong(
            subsong, ss_name, ss_loadmode, ss_rawname, ss_unk1, ss_unk2
        )
        csubsongs.append(csubsong)

    return ImcContainer(csubsongs)


def write_toml(imccontainer, imcname, outerdestdir, progressfunc=None):
    """write an ImcContainer to a plaintext toml file and extracted .sub.imc files

    imccontainer: ImcContainer instance
    name: determines the name of the toml dir & toml file, e.g. "ST00A"
    outerdestdir: directory to which to write the dir containing toml file + subsongs
    progressfunc: function to run whenever a subsong is about to be extracted from
      the ImcContainer. It must accept three arguments: an int subsong index,
      an int total number of subsongs, and an imccontainer.ContainerSubsong instance
    """

    # for zero-padding the number in the filename of each extracted subsong, 03 vs 003
    if imccontainer.num_subsongs <= 100:
        ssidx_width = 2
    else:
        ssidx_width = len(str(imccontainer.num_subsongs - 1))

    # prepare toml dir and toml file. writing a bit early here, but if dir/file can't be
    # written, it's better to error before the time-consuming part instead of after
    tomldir = os.path.join(outerdestdir, imcname)
    tomlpath = os.path.join(tomldir, f"{imcname}{IMCTOML_EXT}")
    os.makedirs(tomldir, exist_ok=True)
    with open(tomlpath, "wt", encoding="utf-8") as tomlfile:
        try:

            tomldoc = tomlkit.parse(_toml_header)
            tomldoc["Repack-Settings"]["max-size"] = "TODO"  # TODO
            tomldoc.add("Subsong", tomlkit.aot())

            for ssidx, csubsong in enumerate(imccontainer.csubsongs):
                if progressfunc is not None:
                    progressfunc(ssidx, imccontainer.num_subsongs, csubsong)

                # Extract subsong to file
                ss_basefilename = f"{ssidx:0{ssidx_width}}.{csubsong.name}{SUBIMC_EXT}"
                # sanitize dir separators out of filename so it doesn't screw up
                ss_basefilename = ss_basefilename.replace(os.path.sep, "_")
                with open(os.path.join(tomldir, ss_basefilename), "wb") as subsongfile:
                    subsongfile.write(csubsong.get_imcdata())

                # Gather & add this subsong's info to toml document
                tomlsubsong = tomlkit.table()
                tomlsubsong["name"] = csubsong.name
                tomlsubsong["loadmode"] = csubsong.loadmode
                tomlsubsong["basefile"] = ss_basefilename
                channel_nums = "".join(
                    str(x) for x in range(1, csubsong.num_channels + 1)
                )
                comment = (
                    f'channels-{channel_nums} = "'
                    f"replacement-audio{SUBSONG_FORMATS['wav']}"
                    '"'
                )
                tomlsubsong.add(tomlkit.comment(comment))

                # Gather & add this subsong's patch-friendly-info to toml document,
                # omitting anything with a None value
                tomlpatchfinfo = tomlkit.table().indent(4)
                if csubsong.rawname is not None:
                    # bytes to ints
                    tomlpatchfinfo["rawname"] = [x for x in csubsong.rawname]
                if not (csubsong.unk1, csubsong.unk2) == (None, None):
                    unk1 = 0 if csubsong.unk1 is None else csubsong.unk1
                    unk2 = 0 if csubsong.unk2 is None else csubsong.unk2
                    tomlpatchfinfo["unk"] = [unk1, unk2]
                # saving original block layout
                if csubsong.original_block_layout is not None:
                    ofbp, obpc = csubsong.original_block_layout
                    # convert from possibly a tomlkit Integer (which retains indent) to
                    # a plain ol' int to prevent indent problems when rewritten to toml
                    ofbp, obpc = int(ofbp), int(obpc)
                    if ofbp is not None:
                        tomlpatchfinfo["frames-per-block"] = ofbp
                    if obpc is not None:
                        tomlpatchfinfo["blocks-per-channel"] = obpc
                if tomlpatchfinfo:  # if tomlpatchfinfo is empty, we won't bother
                    tomlsubsong.add("patch-friendly-info", tomlpatchfinfo)

                # noinspection PyArgumentList
                tomldoc["Subsong"].append(tomlsubsong)

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

        tomlfile.write(tomldoc.as_string())
