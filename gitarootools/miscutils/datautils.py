#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""datautils.py - utility functions for handling data"""

import contextlib
import struct
from math import ceil

if hasattr(contextlib, "nullcontext"):
    nullcontext = contextlib.nullcontext
else:
    # Python 3.6 compatible equivalent
    @contextlib.contextmanager
    def nullcontext(as_value=None):
        yield as_value


def chunks(seq, n, fillseq=None):
    """yield n-sized chunks from seq

    seq: a sequence to be chunked
    n: desired size of each chunk
    fillseq: If the last chunk would be shorter than length n, it will be extended to
    length n by concatenating it with fillseq repeating. If specified, it should
    support being multiplied and added to seq. If not specified, the last chunk can
    be shorter than n.
    yields: sequences of the same type as seq
    raises: ValueError if n==0
    """
    if n == 0:
        raise ValueError("Invalid chunk size 0")

    seq_len = len(seq)
    num_leftovers = seq_len % n
    short_len = seq_len - num_leftovers

    for i in range(0, short_len, n):
        yield seq[i : i + n]

    # handle leftovers
    if num_leftovers:
        if fillseq is None:
            # yield last chunk as-is
            yield seq[short_len:]
        else:
            # extend last chunk and yield it
            num_tofill = n - num_leftovers
            fillseq_extended = fillseq * ceil(num_tofill / len(fillseq))
            yield seq[short_len:] + fillseq_extended[:num_tofill]


def from_nibbles(bytes_, signed=False):
    """yield 4-bit nibble values in bytes_, low nibbles first

    (order example: nibbles(b'\x21\x43\x65') yields the nibbles 1,2,3,4,5,6)

    bytes_: a bytes object OR a single int representing a single byte.
    signed: if True, nibbles are yielded as signed values,
        i.e. nibbles between [0x8 to 0xf] will yield respective values [-8 to -1]
    yields: integers in the range 0,15 for signed=False, -8,7 for signed=True
    """
    if not hasattr(bytes_, "__iter__"):
        bytes_ = (bytes_,)
    for b in bytes_:
        if signed:
            yield -(b & 0b1000) + (b & 0b0111)
            yield -(b >> 4 & 0b1000) + (b >> 4 & 0b0111)
        else:
            yield b & 0b1111
            yield (b >> 4) & 0b1111


def to_nibbles(*nibblevals):
    """return nibblevals encoded as bytes. the lower nibble of each byte is filled first

    (order example: to_nibbles(1,2,3,4,5,6) will return b'\x21\x43\x65')

    nibblevals: iterator of nibble values (ints in the range [-8,15])
    returns: bytes object
    raises: ValueError if an odd number of nibblevals is passed
    """
    nibblevals = tuple(nibblevals)
    if len(nibblevals) % 2:
        raise ValueError("number of nibble values needs to be even")

    return bytes(
        ((high & 0xF) << 4) + (low & 0xF) for low, high in chunks(nibblevals, 2)
    )


def readstruct(fmt, file):
    """read and return values from file according to struct fmt

    fmt: string struct format (see documentation for builtin struct module)
    file: file object with read(size) method
    returns: If it's just one value, it's return directly (not in a tuple).
        Multiple values are still returned as a tuple.
    raises: EOFError if end of file is encountered before all bytes are read
    """
    size = struct.calcsize(fmt)
    data = file.read(size)
    if len(data) < size:
        raise EOFError(
            f"Tried to read {size} bytes from file, but there were only {len(data)} "
            "bytes remaining"
        )
    ret = struct.unpack(fmt, data)
    if len(ret) == 1:
        ret = ret[0]
    return ret


def readdata(file, size):
    """read and return data from file

    file: file object with read(size) method
    size: read this many bytes
    returns: bytes object of data read
    raises: EOFError if end of file is encountered before all bytes are read
    """
    data = file.read(size)
    if len(data) < size:
        raise EOFError(
            f"Tried to read {size} bytes from file, but there were only {len(data)} "
            "bytes remaining"
        )
    return data


def open_maybe(file, mode="r", **kwargs):
    """a drop-in replacement for open() that can also take an already-opened file

    Like open(), open_maybe() can be used in a with statement.
    Differences from builtin open():
    - First argument can be an already-opened file object instead of a path.
    - If given an already-opened file, it will not be closed when the context manager/
      with statement ends.
    """
    # check if it's already a file
    if hasattr(file, "read") or hasattr(file, "write"):
        return nullcontext(file)
    else:
        # it's not already a file, so open one
        return open(file, mode, **kwargs)


def clamp(val, min_, max_):
    """clamp val to between min_ and max_ inclusive"""
    if val < min_:
        return min_
    if val > max_:
        return max_
    return val


def interleave_uneven(iter1, iter2):
    """alternately yield elements from iter1 and iter2, even if lengths don't match

    if the end of one iterator is reached first, continue to yield from the remaining
    one, e.g. interleave_uneven([1,2], [a,b,c,d]) yields 1,a,2,b,c,d
    """
    list1, list2 = list(iter1), list(iter2)
    while 1:
        if list1:
            yield list1.pop(0)
        else:
            yield from list2
            return
        if list2:
            yield list2.pop(0)
        else:
            yield from list1
            return
