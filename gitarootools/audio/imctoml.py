# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
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

from gitarootools.audio.imccontainer import ContainerSubsong, ImcContainer
from gitarootools.audio.subsong import read_subsong
from gitarootools.miscutils.extutils import SUBSONG_FORMATS

SUBIMC_EXT = SUBSONG_FORMATS["subimc"]


class ImcTomlError(Exception):
    """base class for IMC TOML errors"""

    pass


class ChannelReplacementError(ImcTomlError):
    """class for errors carrying out channel replacement"""

    pass


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
    # [[Subsong]] entries below.
    name = "SUBSONG"
    # name: Used internally by the game. Must be 16 ascii characters or less.
    loadmode = "stream"
    # loadmode: Memory loading mode, either "stream" or "entire".
    # "stream" will load only part at a time as it plays, typically used for music.
    # "entire" will load the whole thing in advance, typically used for sound effects.
    basefile = "00.SUBSONG.sub.imc"
    # basefile: Audio file containing this subsong's audio.
    # Option 1: You can change this to point to another file (such as a WAV file).
    # Option 2: You can use this file as-is and override only specific channels with
    # another file's (see below). If you don't need to modify every channel, Option 2 is
    # recommended because when you recompress a channel, it adds recompression noise and
    # increases the size of the binary diff patch.
    channels-43-to-56 = "00.OTHER.wav"
    # channels-#-to-#: Use this audio file to override the basefile's channels.
    # Here channels 4 and 3 of this file will override channels 5 and 6 of the basefile
    # in that exact order. (Note: channels are numbered starting from 1, not 0.)
    channels-to-56 = "00.OTHER.wav"
    # channels-to-#: Shorthand alternative to the above.
    # The first set of channels will be automatically filled in with channels (1,2,3...)
    # equal to the number of destination channels. In this example, channels 1 and 2 of
    # this WAV file will override channels 5 and 6 of the basefile above.
    # (Advanced usage: You can specify multiple "channels-" entries to get channels from
    # more than one input file.)
    [diff-patch-info]
    # Everything in this section can be safely left alone. It was automatically filled
    # with data from the original game. If [Repack-Settings].diff-patch-friendly = true,
    # this is used to match the original data's layout, reducing binary diff patch size.

[Repack-Settings]
    # Settings used by gm-imcpack during the repacking process. Comment out an entry to
    # disable it. (These can also be overridden by passing the relevant arguments to
    # gm-imcrepack.)
    diff-patch-friendly = true
    # diff-patch-friendly: If this exists and is true, the repacked IMC container will
    # closely match the layout of original, resulting in a smaller binary diff patch.
    # (This uses the [diff-patch-info] sections below, ignoring any missing sections
    # or info.)

"""


class SubsongChannelReplacer:
    """helper class to replace a subsong.Subsong instance's channels with another's"""

    def __init__(self, subsong_dest, dest_filename, dest_intname):
        """instantiate a channel replacer for this subsong.Subsong instance

        subsong_dest: a subsong.Subsong instance whose channels are to be replaced
        The following are only used create useful error messages:
          dest_filename: name of the file subsong_dest came from (basename only)
          dest_intname: internal name of subsong_dest (from the IMC container's entries)
        """
        self._already_replaced_channels = dict()
        self._subsong_dest = subsong_dest
        self._dest_filename = dest_filename
        self._dest_intname = dest_intname

    def _chnums_from_chstring(self, chsrepl_string):
        """from a str like "channels-to-56" or "channels-43-to-56", get src/dest channels

        "channels-to-56" returns ((1,2), (5,6))
        "channels-43-to-56" returns ((4,3), (5,6))
        "channels-56" is for backwards compatibility, returns ((5,6), (5,6))

        chsrepl_string: a string like "channels-to-56" or "channels-43-to-56"
        returns: (chanrepl_src, chanrepl_dest)
          chanrepl_src: a tuple of ints representing source channels
          chanrepl_dest: a tuple of ints representing destination channels

        """
        chnums_raw = chsrepl_string[
            len("channels-") :
        ]  # e.g. "56" (old way), "to-34",  or "12-to-56"
        if "to" in chnums_raw:  # chnums_raw = "12-to-56" or "to-34"
            try:
                # "channels-12-to-56" -> src=(1,2) dest=(5,6)
                if "-to-" in chnums_raw:
                    chnums_src, chnums_dest = (
                        tuple(int(x) for x in chnums_srcdest_raw)
                        for chnums_srcdest_raw in chnums_raw.split("-to-", maxsplit=1)
                    )
                # "channels-to-34" -> src=(1,2) dest=(3,4)
                elif chnums_raw.startswith("to-"):
                    chnums_dest = tuple(int(x) for x in chnums_raw[3:])
                    chnums_src = tuple(range(1, len(chnums_dest) + 1))
                else:
                    raise ValueError()
            except ValueError:
                raise ChannelReplacementError(
                    f"subsong {self._dest_intname}: "
                    "Channel replacement key name needs to be in a format like "
                    "'channels-56' or 'channels-12-to-56', "
                    f"not {chsrepl_string!r}"
                )
            # sanity check: same number of src and dest channels
            if not len(chnums_src) == len(chnums_dest):
                raise ChannelReplacementError(
                    f"subsong {self._dest_intname}: "
                    "Channel replacement key name needs an equal number of digits on "
                    'either side of "-to-", '
                    f"not {chsrepl_string!r}"
                )

        else:  # "channels-56", only here for backwards compatibility
            # "56" -> (5,6) -> src=(5,6) dest=(5,6)
            try:
                chnums_dest = tuple(int(x) for x in chnums_raw)
            except ValueError:
                raise ChannelReplacementError(
                    f"subsong {self._dest_intname}: "
                    "Channel replacement key name needs to be in a format like "
                    "'channels-12-to-56' or 'channels-to-56', "
                    f"not {chsrepl_string!r}"
                )
            chnums_src = chnums_dest

        return chnums_src, chnums_dest

    def replace_channels(self, subsong_src, chanrepl_string, subsong_src_filename):
        """replce dest subsong's channels with src's based on chanrepl_string

        Channels in subsong_src replace channels in self._subsong_dest, based on
        chanrepl_string.

        subsong_src: a subsong.Subsong instance
        chanrepl_string: a string like "channels-56" or "channels-43-to-56", specifying
          which channels to take from subsong_src and which to replace in subsong_dest
          (channels are numbered starting from 1)
        subsong_src_filename: filename that subsong_src came from (basename only).
          Only used to create useful error messages.
        """
        subsong_dest = self._subsong_dest
        chnums_src, chnums_dest = self._chnums_from_chstring(chanrepl_string)
        already_replaced_channels = self._already_replaced_channels

        for chnum_src, chnum_dest in zip(chnums_src, chnums_dest):
            if chnum_dest in already_replaced_channels:
                prev_filename, prev_src = already_replaced_channels[chnum_dest]
                warnings.warn(
                    f"subsong {self._dest_intname}: "
                    f"{self._dest_filename} channel {chnum_dest} was already "
                    f"replaced by {prev_filename} channel {prev_src}, "
                    "is being replaced again by "
                    f"{subsong_src_filename} channel {chnum_src}",
                    ChannelAlreadyReplacedWarning,
                )
            already_replaced_channels[chnum_dest] = (subsong_src_filename, chnum_src)
            chidx_src = chnum_src - 1
            chidx_dest = chnum_dest - 1
            try:
                subsong_dest.channels[chidx_dest] = subsong_src.channels[chidx_src]
            except IndexError:
                if chidx_src >= subsong_src.num_channels:
                    oob_kind = "replacement"
                    oob_name = subsong_src_filename
                    oob_numchannels = subsong_src.num_channels
                    oob_oobchannel = chnum_src
                else:
                    oob_kind = "basefile"
                    oob_name = self._dest_filename
                    oob_numchannels = subsong_dest.num_channels
                    oob_oobchannel = chnum_dest
                raise ChannelReplacementError(
                    f"subsong {self._dest_intname}: "
                    f"Channel replacement entry {chanrepl_string!r} out of bounds, "
                    f"{oob_kind} {oob_name!r} only contains "
                    f"{oob_numchannels} channels, not {oob_oobchannel}"
                )


def read_toml(tomlpath):
    """read an ImcContainer from a toml file and its subsong files

    tomlpath: path to the toml file. Any subsong files referenced within must be
      contained in the same dir as tomlpath
    """
    tomldir = os.path.dirname(tomlpath)
    with open(tomlpath, "rt", encoding="utf-8") as tomlfile:
        tomldoc = tomlkit.parse(tomlfile.read())

    if "Repack-Settings" in tomldoc:
        diff_friendly = tomldoc["Repack-Settings"].get("diff-patch-friendly", False)
    else:
        diff_friendly = False

    if "Subsong" not in tomldoc:
        return ImcContainer([])

    csubsongs = []
    for tomlsubsong in tomldoc["Subsong"]:

        # 1. read ContainerSubsong info from TOML
        ss_name = tomlsubsong["name"]
        ss_loadmode = tomlsubsong["loadmode"]
        ss_basefile = tomlsubsong["basefile"]

        # 2. read diff-patch-info if desired & possible
        ss_rawname = ss_unk1 = ss_unk2 = ofpb = obpc = None
        if diff_friendly:
            tomldiffpinfo = tomlsubsong.get("diff-patch-info", None)
            if tomldiffpinfo is not None:
                if "rawname" in tomldiffpinfo:
                    ss_rawname = bytes(tomldiffpinfo["rawname"])
                if "unk" in tomldiffpinfo:
                    ss_unk1, ss_unk2 = tomldiffpinfo["unk"]
                if "frames-per-block" in tomldiffpinfo:
                    ofpb = tomldiffpinfo["frames-per-block"]
                if "blocks-per-channel" in tomldiffpinfo:
                    obpc = tomldiffpinfo["blocks-per-channel"]

        # 3. read subsong from .wav or .sub.imc file
        subsongpath = os.path.join(tomldir, ss_basefile)
        subsong = read_subsong(subsongpath)

        # 4. restore subsong's original block layout from TOML if desired & possible
        # (only if diff-patch-friendly==True and this info exists in the TOML)
        subsong.original_block_layout = (ofpb, obpc)

        # 5. process subsong channel replacement entries
        dest_subsong_chreplacer = SubsongChannelReplacer(subsong, ss_basefile, ss_name)
        for key, value in tomlsubsong.items():
            if key.startswith("channels-"):
                # Carry out channel replacement
                subsong_src_filename = value
                subsong_src = read_subsong(os.path.join(tomldir, subsong_src_filename))
                dest_subsong_chreplacer.replace_channels(
                    subsong_src, key, subsong_src_filename
                )

        # 6. convert to a ContainerSubsong (name, loadmode, etc)
        csubsong = ContainerSubsong(
            subsong, ss_name, ss_loadmode, ss_rawname, ss_unk1, ss_unk2
        )
        csubsongs.append(csubsong)

    return ImcContainer(csubsongs)


def write_toml(
    imccontainer, output_dirpath, output_tomlbase, progressfunc=None,
):
    """write an ImcContainer to a plaintext toml file and extracted .sub.imc files

    imccontainer: ImcContainer instance
    output_dirpath: new directory to create and to unpack IMC contents to
    output_tomlbase: base filename to which to write the .IMC.toml file (will be put in
      output_dirpath)
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
    tomldir = output_dirpath
    tomlpath = os.path.join(tomldir, output_tomlbase)
    os.makedirs(tomldir, exist_ok=True)
    with open(tomlpath, "wt", encoding="utf-8") as tomlfile:
        try:

            tomldoc = tomlkit.parse(_toml_header)
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
                    f'channels-{channel_nums}-to-{channel_nums} = "'
                    f"replacement-audio{SUBSONG_FORMATS['wav']}"
                    '"'
                )
                tomlsubsong.add(tomlkit.comment(comment))

                # Gather & add this subsong's diff-patch-info to toml document,
                # omitting anything with a None value
                tomldiffpinfo = tomlkit.table().indent(4)
                if csubsong.rawname is not None:
                    # bytes to ints
                    tomldiffpinfo["rawname"] = [x for x in csubsong.rawname]
                if not (csubsong.unk1, csubsong.unk2) == (None, None):
                    unk1 = 0 if csubsong.unk1 is None else csubsong.unk1
                    unk2 = 0 if csubsong.unk2 is None else csubsong.unk2
                    tomldiffpinfo["unk"] = [unk1, unk2]
                # saving original block layout
                if csubsong.original_block_layout is not None:
                    ofbp, obpc = csubsong.original_block_layout
                    # convert from possibly a tomlkit Integer (which retains indent) to
                    # a plain ol' int to prevent indent problems when rewritten to toml
                    ofbp, obpc = int(ofbp), int(obpc)
                    if ofbp is not None:
                        tomldiffpinfo["frames-per-block"] = ofbp
                    if obpc is not None:
                        tomldiffpinfo["blocks-per-channel"] = obpc
                if tomldiffpinfo:  # if tomldiffpinfo is empty, we won't bother
                    tomlsubsong.add("diff-patch-info", tomldiffpinfo)

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
