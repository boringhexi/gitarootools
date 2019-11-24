#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subsong.py - read/write subsong files

A "subsong" can be:
- "IMC subsong": a PS-ADPCM audio file originating from an IMC audio container file.
  Has extension .sub.imc
- an audio file of a different format (e.g. .wav) that serves the same purpose
"""
# The portions of this file that decode PS-ADPCM data to PCM are derived from vgmstream
# (https://github.com/losnoco/vgmstream) and are therefore covered by some or all of the
# following copyright notice:
#
# Copyright (c) 2008-2019 Adam Gashlin, Fastelbja, Ronny Elfert, bnnm,
#                         Christopher Snowhill, NicknineTheEagle, bxaimc,
#                         Thealexbarney, CyberBotX, et al
#
# Portions Copyright (c) 2004-2008, Marko Kreen
# Portions Copyright 2001-2007  jagarl / Kazunori Ueno <jagarl@creator.club.ne.jp>
# Portions Copyright (c) 1998, Justin Frankel/Nullsoft Inc.
# Portions Copyright (C) 2006 Nullsoft, Inc.
# Portions Copyright (c) 2005-2007 Paul Hsieh
# Portions Public Domain originating with Sun Microsystems


import struct
import wave
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from io import SEEK_END
from itertools import chain, repeat, zip_longest
from math import ceil

from gitarootools.miscutils.datautils import (
    chunks,
    from_nibbles,
    interleave_uneven,
    open_maybe,
    to_nibbles,
)
from gitarootools.miscutils.extutils import subsongtype

ps_adpcm_coefs = (
    (0.0, 0.0),
    (0.9375, 0.0),
    (1.796875, -0.8125),
    (1.53125, -0.859375),
    (1.90625, -0.9375),
)

# When encoding, for each frame we'll go through every possible combination of
# shift_factor (0 to 12) and coef_idx (0 to 4). It'll go faster if we encounter the
# best combination sooner rather than later. Since we expect each frame to have
# similar values to the previous frame, we will start with shift_factor/coef_idx
# close to the previous frame's. e.g. If the previous frame had coef_idx 2, for the
# current frame we'll test coef_idx in order of (2,1,3,0,4). Below we create lookup
# tables to get the orders quickly as they're needed.
shift_factors_order = dict()
for _i in range(13):
    _order = interleave_uneven(range(_i, 13), reversed(range(_i)))
    shift_factors_order[_i] = tuple(_order)
coefs_order = dict()
for _i in range(5):
    _order = interleave_uneven(range(_i, 5), reversed(range(_i)))
    _coefs = tuple((coef_idx, ps_adpcm_coefs[coef_idx]) for coef_idx in _order)
    coefs_order[_i] = _coefs

# blank frame that ends all Gitaroo Man audio. flag 0x7 means "End marker + don't play"
PSFRAME_ENDBLANK = b"\x00\x07" + b"\x00" * 14
PSFRAME_NUMBYTES = 0x10  # bytes per ps-adpcm frame
PSFRAME_NUMSAMPLES = 28  # samples per ps-adpcm frame


class SubsongError(Exception):
    """base class for subsong-related exceptions"""

    pass


class EndOfSubsongError(SubsongError, EOFError):
    """raised when the end of a subsong is reached unexpectedly"""

    pass


class BaseChannel(metaclass=ABCMeta):
    """base class for subsong channels"""

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def get_pcm16(self):
        """return 16-bit signed linear PCM samples (list of ints)

        TODO may change this to return a Numpy array instead
        """
        pass

    @abstractmethod
    def get_psadpcm(self):
        """return PS-ADPCM data (bytes)

        Implementation note: Following the format of Gitaroo Man audio:
        - the last audible frame should have flag=0x1 (means "End marker (last frame)")
        - a single blank end frame (PSFRAME_ENDBLANK) should come after the audible
          frames (this should also be reflected by num_psadpcm_frames)
        """
        pass

    @property
    @abstractmethod
    def num_psadpcm_frames(self):
        """number of PS-ADPCM frames that would be returned in get_psadpcm()

        Implementation note: if computing get_psadpcm() is particularly slow, preferably
          make this faster than that
        """
        pass


class PsAdpcmChannel(BaseChannel):
    """Subsong channel that originated from PS-ADPCM audio (aka VAG/Very Audio Good)"""

    def __init__(self, psadpcm_data):
        """psadpcm_data: bytes representing one entire channel of PS-ADPCM frames

        Note that data returned by get_psadpcm() may differ from original psadpcm_data:
        - Padding frames will be removed. This means all frames after the end frame
          (the first frame having flag 0x7, which means "End + don't play this frame")
          or if that doesn't exist, all-zero padding frames at the end.
        - It will ensure the last two frames respectively have flag 0x1 ("End marker
        [last frame]") and flag 0x7, ("End + don't play this frame")
        - If the data didn't already have an end flag 0x7 frame, it will be given one.

        raises: SubsongError if the length of psadpcm_data does not represent a whole
          number of PS-ADPCM frames
        """
        super().__init__()

        # verify length of psadpcm_data
        extrabytes = len(psadpcm_data) % PSFRAME_NUMBYTES
        if extrabytes:
            raise SubsongError(
                "psadpcm_data is not a whole number of frames, "
                f"last frame is only {extrabytes} bytes out of {PSFRAME_NUMBYTES}"
            )

        # remove end/padding frames from the end of get_psadpcm
        discard_frame_idx = 0
        for i, frame in enumerate(chunks(psadpcm_data, PSFRAME_NUMBYTES)):
            if frame[1] == 0x7:
                # discard the first frame having flag=0x7 and all frames after it
                # flag 0x7 means end + don't play this frame
                discard_frame_idx = i
                endframe = frame  # save end frame to re-add later
                break
            if any(frame):
                # Or if no flag 0x7 frame, discard all after the last non-zero frame
                discard_frame_idx = i + 1
        else:
            endframe = PSFRAME_ENDBLANK  # no end frame, so let's create our own
        psadpcm_data = psadpcm_data[: discard_frame_idx * PSFRAME_NUMBYTES]

        # ensure the last audible frame has flag 0x1, meaning "End marker (last frame)"
        if psadpcm_data:
            psadpcm_data = psadpcm_data[:-15] + b"\x01" + psadpcm_data[-14:]

        self._psadpcm_data = psadpcm_data + endframe

    def get_pcm16(self):
        """return 16-bit signed linear PCM samples, converted from PS-ADPCM data

        returns: list of 16-bit signed ints (i.e. in the range -32768, 32767)
        raises: SubsongError on encountering a PS-ADPCM data frame with an invalid
          coef_idx, shift_factor, or flag
        """
        decodedsamples = []
        hist1 = hist2 = 0

        for frame_idx, frame in enumerate(chunks(self._psadpcm_data, PSFRAME_NUMBYTES)):
            shift_factor, coef_idx = from_nibbles(frame[0])
            flag = frame[1]

            # check for invalid values
            errors = []
            if not coef_idx <= 0x4:
                errors.append(f"invalid coef_idx {coef_idx:#x}")
            if not shift_factor <= 0xC:
                errors.append(f"invalid shift_factor {shift_factor:#x}")
            if not flag <= 0x7:
                errors.append(f"invalid flag {flag:#x}")
            if errors:
                raise SubsongError(f"Frame {frame_idx} has " + " and ".join(errors))

            for nibble in from_nibbles(frame[2:], signed=True):
                # To turn a nibble into a sample:
                # 1. multiply nibble by a biggish value
                sample = nibble * 2 ** (12 - shift_factor)
                # 2. adjust a little based on the previous sample
                sample += ps_adpcm_coefs[coef_idx][0] * hist1
                # 3. and adjust again based on the sample before that
                sample += ps_adpcm_coefs[coef_idx][1] * hist2
                # 4 clamp to 16-bit signed int
                if sample <= -32768:
                    sample = -32768
                elif sample >= 32767:
                    sample = 32767
                else:
                    sample = int(sample)

                decodedsamples.append(sample)
                hist2 = hist1
                hist1 = sample

        return decodedsamples

    def get_psadpcm(self):
        """return PS-ADPCM data (bytes)"""
        return self._psadpcm_data

    @property
    def num_psadpcm_frames(self):
        """number of PS-ADPCM frames that would be returned in get_psadpcm()"""
        return len(self._psadpcm_data) // PSFRAME_NUMBYTES


class Pcm16Channel(BaseChannel):
    """A single subsong channel that originated from linear PCM 16-bit signed samples"""

    def __init__(self, pcm_samples):
        """pcm_samples: (iterable of ints) 16-bit signed linear PCM samples"""
        super().__init__()

        self._pcm_samples = list(pcm_samples)
        # TODO maybe storing as numpy array is better

    def get_pcm16(self):
        """return 16-bit signed linear PCM samples (list of ints)"""
        return self._pcm_samples

    def get_psadpcm(self):
        """return PS-ADPCM data (bytes), converted from 16-bit PCM samples

        Note that, following the format of Gitaroo Man audio:
        - the last audible frame will have flag 0x1 (meaning "End marker (last frame)")
        - audible frames will be followed by a single blank frame with flag 0x7 (meaning
          "End + don't play this frame")
        """
        num_audible_frames = self.num_psadpcm_frames - 1
        if num_audible_frames <= 0:
            return PSFRAME_ENDBLANK

        # set up the stuff we'll be iterating through
        frames_samples = chunks(self._pcm_samples, PSFRAME_NUMSAMPLES, fillseq=[0])
        # TODO if changing to numpy array..
        flags = chain(repeat(0x0, num_audible_frames - 1), (0x1,))
        # normal frames have flag 0x0, final audible frame has flag 0x1 i.e. "End marker
        #   (last frame)"

        # Now, let's encode each frame one at a time and accumulate the encoded nibble
        #   values in psadpcm_nibblevals
        prev_shift_factor, prev_coef_idx = 0, 0
        psadpcm_nibblevals = []
        hist1 = hist2 = 0

        # for each frame (group of 28 samples):
        for frame_samples, flag in zip(frames_samples, flags):

            if not any(frame_samples):
                # a frame with all 0 samples is easy to encode
                frame_nibblevals = (0, 0, flag, 0) + (0,) * PSFRAME_NUMSAMPLES
                psadpcm_nibblevals.extend(frame_nibblevals)
                hist1 = hist2 = 0
                continue

            # Summary of the nested loop below: We make multiple attempts to encode
            # this frame and keep the best one. For the first attempt, since are no
            # previous attempts to compare to, we encode the whole frame and keep it.
            # For subsequent attempts, we encode each sample to a nibble, re-decode
            # it, and compare the re-decoded sample to the original. Depending on how
            # accurate it is compared to previous attempts, we may encode the whole
            # frame this way and keep it (replacing previous best attempts),
            # or we may give up partway through and move on to the next attempt.

            # shift_factors and coefs: For this frame, we'll test every combination
            # of shift_factor/coef_idx and see which one works the best (i.e. encodes
            # the frame most accurately). We could just use range(13) and range(5),
            # but it's much faster to test in an order based on the previous frame's
            # shift_factor/coef_idx.
            shift_factors = shift_factors_order[prev_shift_factor]
            coefs = coefs_order[prev_coef_idx]
            # bestdiff: an encoded frame's accuracy is measured by its one worst
            # sample (how much it differs from the original sample). This is the best
            # such value we've managed to get so far for this frame.
            bestdiff = None
            best_framevals = None
            best_hists = None

            for shift_factor in shift_factors:
                shiftmul = 2 ** (12 - shift_factor)
                for coef_idx, (coef1, coef2) in coefs:
                    attempt_hist1, attempt_hist2 = hist1, hist2
                    attempt_worstdiff = None
                    attempt_nibbles = []

                    # Let's encode the samples in this frame.
                    for sample in frame_samples:
                        coefval = (attempt_hist1 * coef1) + (attempt_hist2 * coef2)

                        # encode to nibble using these parameters (I may need to add
                        # 0.5 to compensate for integer truncation during decoding,
                        # but I'm not sure)
                        nibble = (sample + 0.5 - coefval) / shiftmul
                        # clamp to nearest 4-bit signed int
                        if nibble <= -8:
                            nibble = -8
                        elif nibble >= 7:
                            nibble = 7
                        else:
                            nibble = round(nibble)

                        # re-decode nibble
                        desample = nibble * shiftmul + coefval
                        # clamp to 16-bit signed int
                        if desample <= -32768:
                            desample = -32768
                        elif desample >= 32767:
                            desample = 32767
                        else:
                            desample = int(desample)

                        # difference between original sample and the result of decoding
                        # the encoded sample
                        diff = abs(sample - desample)
                        if bestdiff is not None and diff >= bestdiff:
                            # diff is too big for these parameters to be an improvement
                            break  # give up on these parameters and move on to next
                        if attempt_worstdiff is None or diff > attempt_worstdiff:
                            attempt_worstdiff = diff

                        attempt_nibbles.append(nibble)
                        attempt_hist2 = attempt_hist1
                        attempt_hist1 = desample

                    else:
                        # We didn't hit the `break` and give up partway through
                        # frame_samples, which means we now have an improvement over
                        # previous attempts. (Note that due to bestdiff's initial
                        # value, it will never give up partway through the first
                        # attempt)
                        bestdiff = attempt_worstdiff
                        best_framevals = (
                            shift_factor,
                            coef_idx,
                            flag,
                            0,
                            *attempt_nibbles,
                        )
                        best_hists = (attempt_hist1, attempt_hist2)

            # At this point, we've tried every shift_factor/coef_idx, so now
            # best_framevals has what we want
            psadpcm_nibblevals.extend(best_framevals)
            hist1, hist2 = best_hists
            prev_shift_factor, prev_coef_idx = best_framevals[:2]

        # At this point, psadpcm_nibblevals contains all our nibbles values,
        # they need to be turned into bytes
        return to_nibbles(*psadpcm_nibblevals) + PSFRAME_ENDBLANK

    @property
    def num_psadpcm_frames(self):
        """number of PS-ADPCM frames that would be returned in get_psadpcm()"""
        num_audible_frames = ceil(len(self._pcm_samples) / PSFRAME_NUMSAMPLES)
        return num_audible_frames + 1  # for blank flag=0x7 ending frame


SubsongBlockLayout = namedtuple(
    "SubsongBlockLayout", "frames_per_block, blocks_per_channel"
)


class Subsong:
    def __init__(self, channels, sample_rate, ofpb=None, obpc=None):
        """initialize a subsong of sample_rate from channels

        channels: iterable of channels (e.g. PsAdpcmChannel and/or Pcm16Channel objects)
        sample_rate: samples per second, can be 22000 to 48000 inclusive
        ofpb, obpc: assigns self.original_block_layout = (ofpb, obpc), see that for info

        """
        self.channels = list(channels)
        self.sample_rate = sample_rate
        self.original_block_layout = (ofpb, obpc)

    @property
    def original_block_layout(self):
        """original block layout (frames_per_block, blocks_per_channel) or None

        This value is used to by self.get_imcdata() to output the original block
        layout, allowing it to closely match the original Gitaroo Man subsong for the
        creation of a smaller binary diff patch.

        This property can be assigned either:
         - None
         - a 2-iterable containing one or more None (same effect as assigning None)
         - a 2-iterable of ints
        When accessed, this property may contain either:
        - None
        - a named tuple with int fields (frames_per_block, blocks_per_channel)
        """
        return self._original_block_layout

    @original_block_layout.setter
    def original_block_layout(self, value):
        if value is None:
            self._original_block_layout = None
        else:
            fpb, bpc = value
            if fpb is not None and bpc is not None:
                self._original_block_layout = SubsongBlockLayout(fpb, bpc)
            else:
                self._original_block_layout = None

    @property
    def sample_rate(self):
        """can be between 22000 and 48000 (inclusive)"""
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, value):
        if not 22000 <= value <= 48000:
            raise ValueError("sample_rate must be between 22000 and 48000")
        self._sample_rate = value

    @property
    def num_channels(self):
        """number of channels"""
        return len(self.channels)

    @property
    def num_frames(self):
        """number of frames (in the longest channel)"""
        return max(ch.num_psadpcm_frames for ch in self.channels)

    def get_imcdata(self, entire=False):
        """interleaves and returns subsong's PS-ADPCM data, including header

        PS-ADPCM data is returned with a certain number of frames per block (fpb) and
        blocks per channel (bpc). There are 3 possibilities, in this order of priority:
        - use self.original_block_layout's saved fpb/bpc if it has them
        - if entire==True, use large fpb + just enough bpc to hold the data
        - otherwise, use 768 fpb + just enough bpc to hold the data
        "entire" is for sound effects but not music, "otherwise" is for both (sfx/music)
        """
        # 1. decide block layout
        if self.original_block_layout is not None:
            frames_per_block, blocks_per_channel = self.original_block_layout
        elif entire:
            # some arbitrary maximum number of frames we'll allow in a single block:
            max_frames_per_block = 32767  # (higher values may work too, haven't tested)
            # if too many frames for a single block, we'll divide them evenly to fit
            divisor = ceil(self.num_frames / max_frames_per_block)
            frames_per_block, blocks_per_channel = ceil(self.num_frames / divisor), None

        else:
            frames_per_block, blocks_per_channel = 768, None

        # 2. create PS-ADPCM header
        num_blocks = self.num_channels * (
            blocks_per_channel
            if blocks_per_channel is not None
            else ceil(self.num_frames / frames_per_block)
        )
        psadpcm_header = struct.pack(
            "<4I", self.num_channels, self.sample_rate, frames_per_block, num_blocks
        )

        # 3. create PS-ADPCM data (divide channels into blocks & interleave them)
        bytes_per_block = PSFRAME_NUMBYTES * frames_per_block
        # a. start with each channel
        #   [ch1data, ch2data]
        channel_datas = (ch.get_psadpcm() for ch in self.channels)
        # if necessary, pad each channel to reach blocks_per_channel
        if blocks_per_channel is not None:
            bytes_per_channel = bytes_per_block * blocks_per_channel
            channel_datas = (
                chdata + b"\0" * (bytes_per_channel - len(chdata))
                for chdata in channel_datas
            )
        # b. chunk each channel into into a list of blocks:
        #   [(ch1block, ch1block, ...), (ch2block, ch2block, ...)]
        #   last block will be zero-padded to a full block
        channel_groups = (
            chunks(channel_data, bytes_per_block, fillseq=b"\0")
            for channel_data in channel_datas
        )
        # c. rearrange the lists of blocks into lists of interleaved blocks:
        #   [(ch1block, ch2block), (ch1block, ch2block), ...]
        interleaved_groups = zip(*channel_groups)
        # d. flatten the lists of interleaved blocks into 1 list of interleaved_blocks:
        #   [ch1block, ch2block, ch1block, ch2block ...]
        interleaved_blocks = chain.from_iterable(interleaved_groups)
        # e. join the interleaved blocks into psadpcm_data:
        #   ch1block-ch2block-ch1block-ch2block-...
        psadpcm_data = b"".join(interleaved_blocks)

        return psadpcm_header + psadpcm_data


def read_subsong(filepath):
    """read a subsong from a file path

    filepath: path to subsong file, extension determines which input format to read as
    """
    sstype = subsongtype(filepath)
    if sstype == "subimc":
        return read_subimc(filepath)
    elif sstype == "wav":
        return read_subwav16(filepath)


def write_subsong(subsong, filepath):
    """write a subsong to a subsong filepath

    filepath: path to write to, extension determines which output format to write as
    """
    sstype = subsongtype(filepath)
    if sstype == "subimc":
        return write_subimc(subsong, filepath)
    elif sstype == "wav":
        return write_subwav16(subsong, filepath)


def read_subimc(file, knownsize=None):
    """read from a IMC subsong file and return a Subsong

    file: A file path. Or it can be an already-opened file, in which case:
    - it will read starting from the current file position
    - after returning, file position will be right after the subsong file data
    - the caller is responsible for closing the file afterwards
    knownsize: Optional size of the IMC subsong file known in advance. It's only used
      for a quick sanity check (to anticipate reading past end of the subsong). Without
      this, it assumes this subsong ends when the file ends, so it's recommended to pass
      this if reading this subsong from inside a larger container file.
    raises:
    - SubsongError if IMC subsong header is invalid
    - EndOfSubsongError if end of subsong is reached unexpectedly
    """
    with open_maybe(file, "rb") as file:
        # Read imc subsong header
        header = file.read(16)
        if len(header) != 16:
            raise EndOfSubsongError(
                "Expected 16 bytes for IMC subsong header, only got"
                f"{len(header)} bytes"
            )
        num_channels, sample_rate, frames_per_block, num_blocks = struct.unpack(
            "<4I", header
        )

        # sanity checks, since the format is so simple
        if not 1 <= num_channels <= 8:
            raise SubsongError(f"invalid number of channels {num_channels}")
        if not 22000 <= sample_rate <= 48000:
            raise SubsongError(f"invalid sample rate {sample_rate}")
        if frames_per_block == 0:
            raise SubsongError("frames per block should not be 0")
        if num_blocks == 0:
            raise SubsongError("number of blocks should not be 0")
        if not num_blocks % num_channels == 0:
            raise SubsongError(
                f"number of channels ({num_channels}) does not divide evenly into"
                f"number of blocks ({num_blocks})"
            )

        # quick check for premature end of file
        if knownsize is None:
            # assume subsong ends when the file ends
            oldtell = file.tell()
            file.seek(0, SEEK_END)
            real_datasize = file.tell() - oldtell
            file.seek(oldtell)
        else:
            real_datasize = knownsize - 0x10  # size - header
        predicted_datasize = PSFRAME_NUMBYTES * frames_per_block * num_blocks
        if predicted_datasize > real_datasize:
            raise EndOfSubsongError(
                f"IMC subsong header predicts {predicted_datasize} bytes of data, "
                f"but only {real_datasize} bytes remain in file"
            )

        bytes_per_block = PSFRAME_NUMBYTES * frames_per_block

        # Deinterleave file data, separating the blocks into channels:
        # starting with one big lump of interleaved_data:
        #   ch1block-ch2block-ch1block-ch2block-...
        interleaved_data = file.read(bytes_per_block * num_blocks)
        # chunk interleaved data into interleaved_blocks:
        #   [ch1block, ch2block, ch1block, ch2block ...]
        interleaved_blocks = tuple(chunks(interleaved_data, bytes_per_block))
        del interleaved_data  # now in interleaved_blocks, no point in keeping
        # group interleaved blocks into interleaved_groups:
        #   [(ch1block, ch2block), (ch1block, ch2block), ...]
        interleaved_groups = chunks(interleaved_blocks, num_channels)
        # deinterleave interleaved_groups into channel_groups:
        #   [(ch1block, ch1block, ...), (ch2block, ch2block, ...)]
        channel_groups = zip(*interleaved_groups)
        # join each channel group into a one big lump of channel data:
        #   [ch1block-ch1block-..., ch2block-ch2block-...]
        channel_datas = (b"".join(channel_group) for channel_group in channel_groups)

    # create Subsong from each channel_data
    channelobjs = []
    for channel_data in channel_datas:
        chobj = PsAdpcmChannel(channel_data)
        channelobjs.append(chobj)
    blocks_per_channel = int(num_blocks / num_channels)
    return Subsong(channelobjs, sample_rate, frames_per_block, blocks_per_channel)


def read_subwav16(file):
    """read a Subsong from a WAV file (16-bit signed linear PCM)

    file: A file path. Or it can be an already-opened file, in which case:
    - it will read starting from the current file position
    - after returning, file position will probably be right after the wav file, but
      I can't guarantee it since I didn't write the built-in `wave` module
    - the caller is responsible for closing the file afterwards
    raises: SubsongError if wav file's sample format is not 16-bit
    """
    with wave.open(file, "rb") as wavfile:
        if wavfile.getsampwidth() != 2:  # i.e. not 16-bit
            raise SubsongError(
                "Only 16-bit wav files are supported, this wav file is "
                f"{wavfile.getsampwidth() * 8}-bit."
            )

        num_channels = wavfile.getnchannels()
        sample_rate = wavfile.getframerate()
        num_frames = wavfile.getnframes()

        # deinterleave samples
        allsamples = struct.unpack(
            f"<{num_channels * num_frames}h", wavfile.readframes(num_frames)
        )
        # a wav frame is a single sample at the same time from all channels
        frames = chunks(allsamples, num_channels)
        del allsamples
        channels_samples = zip(*frames)

    channels = list()
    for ch_samples in channels_samples:
        ch = Pcm16Channel(ch_samples)
        channels.append(ch)
    return Subsong(channels, sample_rate)


def write_subimc(subsong, file):
    """write a Subsong to IMC subsong file

    subsong: a Subsong instance
    file: A file path. Or it can be an already-opened file, in which case:
    - it will write starting from the current file position. After returning, the file
      position will be at the end of the IMC subsong data it just wrote.
    - the caller is responsible for closing the file afterwards
    """
    with open_maybe(file, "wb") as file:
        file.write(subsong.get_imcdata())


def write_subwav16(subsong, file):
    """write a Subsong to WAV file (16-bit signed linear PCM)

    subsong: a Subsong object
    file: A file path. Or it can be an already-opened file, in which case:
    - it will write starting from the current file position
    - after returning, file position will probably be at the end of the wav file, but
      I can't guarantee it since I didn't write the built-in `wave` module
    - the caller is responsible for closing the file afterwards
    """
    with wave.open(file, "wb") as wavfile:
        num_channels = subsong.num_channels
        wavfile.setnchannels(num_channels)
        wavfile.setsampwidth(2)  # i.e. 16-bit
        wavfile.setframerate(subsong.sample_rate)

        pcm16_channels = (ch.get_pcm16() for ch in subsong.channels)
        # a wav frame is a single sample at the same time from all channels
        frames = zip_longest(*pcm16_channels, fillvalue=0)
        packed_frames = (struct.pack(f"<{num_channels}h", *frame) for frame in frames)
        wavfile.writeframesraw(b"".join(packed_frames))
