# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""imximage.py - read/write IMX image files

An IMX image file is a file type from Gitaroo Man that has the extension .IMX
and contains RGB(A) or indexed image data."""
import os
import pathlib
from itertools import chain
from os import SEEK_CUR
from typing import AnyStr, BinaryIO, Optional, Sequence, Tuple, Union

from PIL import Image

from gitarootools.miscutils.cmdutils import my_warn
from gitarootools.miscutils.datautils import (
    chunks,
    from_nibbles,
    open_maybe,
    readdata,
    readstruct,
    to_nibbles,
    writestruct,
)

SeqIndexed = Sequence[int]
SeqRGB = Sequence[Tuple[int, int, int]]
SeqRGBA = Sequence[Tuple[int, int, int, int]]
BinaryFp = Union[BinaryIO, AnyStr, pathlib.Path]  # binary file or path

PIXEL_FORMATS = ("rgba32", "rgb24", "i8", "i4")

_pixfmtdata_pixfmt = {
    b"\0\0\0\0\0\0\0\0": "i4",
    b"\1\0\0\0\1\0\0\0": "i8",
    b"\3\0\0\0\2\0\0\0": "rgb24",
    b"\4\0\0\0\2\0\0\0": "rgba32",
}
_pixfmt_pixfmtdata = {v: k for k, v in _pixfmtdata_pixfmt.items()}


class ImxImageError(Exception):
    """base class for IMX image related errors"""

    pass


class EndOfImxImageError(ImxImageError, EOFError):
    """raised when the end of an IMX image is reached unexpectedly"""

    pass


class ImxImage:
    def __init__(
        self,
        width: int,
        height: int,
        pixels: Union[SeqRGB, SeqRGBA, SeqIndexed],
        palette: Optional[SeqRGBA] = None,
        pixfmt: Optional[str] = None,
        alpha128: bool = True,
    ) -> None:
        """initialize an ImxImage

        Note that IMX files consider 128 alpha the most opaque value, rather than 255

        :param width: image width in pixels
        :param height: image height in pixels
        :param pixels: sequence of pixels: either ints (if using palette),
            3-seqs of ints (no palette, RGB), or 4-seqs of ints (no palette, RGBA)
        :param palette: optional sequence of 4-seqs of ints (RGBA)
        :param pixfmt: image pixel format, one of string (rgba32, rgb24, i8, i4)
            or None. If None, pixel format will be automatically chosen.
        :param alpha128: pass True if the pixels or palette use 128 as the alpha
            value representing 100% opacity (as happens when reading from an IMX file).
            Pass False if they use 255 instead (as is done by most other image formats).
        """
        self._width = width
        self._height = height

        if pixfmt is not None:
            if pixfmt not in PIXEL_FORMATS:
                raise ValueError(
                    f"pixfmt must be one of {PIXEL_FORMATS}, was {pixfmt!r}"
                )
            if pixfmt == "i4" and width % 2:
                raise ValueError(
                    f"Pixel format i4 requires an even-numbered width, width={width}"
                )
        else:
            if palette:
                pixfmt = "i4" if (len(palette) <= 16 and width % 2 == 0) else "i8"
            else:  # no palette
                if pixels and max(len(pix) for pix in pixels) == 4:
                    pixfmt = "rgba32"
                else:
                    pixfmt = "rgb24"
        self.pixfmt = pixfmt
        self._alpha128 = alpha128
        self._palette = palette
        self._pixels = pixels

    @property
    def alpha128(self) -> bool:
        """True if image uses 128-based alpha"""
        return self._alpha128

    @property
    def alpha255(self) -> bool:
        """True if image uses 255-based alpha"""
        return not self.alpha128

    @property
    def size(self) -> Tuple[int, int]:
        """(width, height)"""
        return self._width, self._height

    @property
    def haspalette(self) -> bool:
        """True if this image has a palette"""
        return self._palette is not None

    @property
    def hasalpha(self) -> bool:
        """True if this image has an alpha channel"""
        return self.haspalette or (self._pixels and len(self._pixels[0]) == 4)

    @property
    def palette(self) -> Optional[SeqRGBA]:
        """palette, alpha values are based whether self.alpha128 is True or not"""
        return self._palette

    @property
    def palette128(self) -> Optional[SeqRGBA]:
        """palette with 128-based alpha"""
        if self.palette is None:
            return None
        if self.alpha128:
            return self.palette
        elif self.alpha255:
            # get alpha128 = ceil(alpha255/255*128)
            return [
                (r, g, b, int(a255 / 255 * 128 + 0.5))
                for (r, g, b, a255) in self.palette
            ]

    @property
    def palette255(self) -> Optional[SeqRGBA]:
        """palette with 255-based alpha"""
        if self.palette is None:
            return None
        if self.alpha255:
            return self.palette
        elif self.alpha128:
            # get alpha255 = floor(alpha128/128*255)
            return [
                (r, g, b, int(a128 / 128 * 255)) for (r, g, b, a128) in self.palette
            ]

    @property
    def pixels(self) -> Union[SeqRGB, SeqRGBA, SeqIndexed]:
        """pixels, alpha are based on whether self.alpha128 is true or not"""
        return self._pixels

    @property
    def pixels128(self) -> Union[SeqRGB, SeqRGBA, SeqIndexed]:
        """pixels with 128-based alpha"""
        if not self.pixels:
            return []
        if self.palette is None and len(self.pixels[0]) == 4:  # RGBA
            if self.alpha255:
                # get alpha128 = ceil(alpha255/255*128)
                return [
                    (r, g, b, int(a255 / 255 * 128 + 0.5))
                    for (r, g, b, a255) in self.pixels
                ]
            elif self.alpha128:
                return self.pixels
        else:  # RGB or indexed
            return self.pixels

    @property
    def pixels255(self) -> Union[SeqRGB, SeqRGBA, SeqIndexed]:
        """pixels with 255-based alpha"""
        if not self.pixels:
            return []
        if self.palette is None and len(self.pixels[0]) == 4:  # RGBA
            if self.alpha128:
                # get alpha255 = floor(alpha128/128*255)
                return [
                    (r, g, b, int(a128 / 128 * 255)) for (r, g, b, a128) in self.pixels
                ]
            elif self.alpha255:
                return self.pixels
        else:  # RGB or indexed
            return self.pixels


def read_imx(fp: BinaryFp) -> ImxImage:
    """read from an IMX image file and return an ImxImage

    :param fp: A file path. Or it can be an already-opened file, in which case:
        - it will read starting from the current file position
        - after returning, file position will be right after the IMX file data
        - the caller is responsible for closing the file afterwards
    :raises ImxImageError if IMX header is invalid
    :raises EndOfImxImageError if end of IMX data is reached unexpectedly
    :return: ImxImage instance
    """
    with open_maybe(fp, "rb") as file:
        try:
            magic = readdata(file, 4)
            if magic != b"IMX\0":
                raise ImxImageError(f"Not an IMX file, unknown magic {magic!r}")
            width, height, pixfmtdata = readstruct(file, "<16x2I8s")
            pixfmt = _pixfmtdata_pixfmt.get(pixfmtdata)
            if pixfmt is None:
                raise ImxImageError(f"Unknown IMX pixel format data {pixfmtdata!r}")

            if width % 2:
                raise ImxImageError(
                    "indexed-4 pixel format requires width be a multiple of 2, "
                    f"but width={width}"
                )

            if pixfmt in ("i4", "i8"):
                palette_size = readstruct(file, "<I")
                struct_fmt = f"{palette_size}B"
                palette = tuple(chunks(readstruct(file, struct_fmt), 4))
                file.seek(4, SEEK_CUR)  # always 2?
            else:
                palette = None

            pixels_size = readstruct(file, "<I")
            if pixfmt == "i4":
                struct_fmt = f"{pixels_size}B"
                pixels = tuple(from_nibbles(readstruct(file, struct_fmt)))
            elif pixfmt == "i8":
                struct_fmt = f"{pixels_size}B"
                pixels = readstruct(file, struct_fmt)
            elif pixfmt == "rgb24":
                struct_fmt = f"{pixels_size}B"
                pixels = tuple(chunks(readstruct(file, struct_fmt), 3))
            elif pixfmt == "rgba32":
                struct_fmt = f"{pixels_size}B"
                pixels = tuple(chunks(readstruct(file, struct_fmt), 4))

            # footer
            file.seek(8, SEEK_CUR)  # always uint32s (3,0)?

        except EOFError as e:
            raise EndOfImxImageError(str(e))

    return ImxImage(width, height, pixels, palette, pixfmt=pixfmt, alpha128=True)


def write_imx(imximage: ImxImage, fp: BinaryFp) -> None:
    """write imximage to file

    :param imximage: an ImxImage instance
    :param fp: A file path. Or it can be an already-opened file, in which case:
        - it will write starting from the current file position
        - after returning, file position will be right after the written IMX data
        - the caller is responsible for closing the file afterwards
    """
    with open_maybe(fp, "wb") as file:
        # header
        file.write(b"IMX\0")
        pixfmtdata = _pixfmt_pixfmtdata[imximage.pixfmt]
        writestruct(file, "<16x2I8s", *imximage.size, pixfmtdata)

        # palette
        if imximage.pixfmt in ("i4", "i8"):
            palette = imximage.palette128
            palette_num_bytes = len(palette) * 4
            writestruct(file, "<I", palette_num_bytes)
            writestruct(file, f"{palette_num_bytes}B", *chain.from_iterable(palette))
            writestruct(file, "<I", 2)

        # pixels
        pixels = imximage.pixels128
        if imximage.pixfmt == "i8":
            pixels_flat = pixels  # already flat
        elif imximage.pixfmt == "i4":
            pixels_flat = tuple(to_nibbles(*pixels))
        else:
            pixels_flat = tuple(chain.from_iterable(pixels))  # flatten (r,g,b) stuff
        pixels_num_bytes = len(pixels_flat)
        writestruct(file, "<I", pixels_num_bytes)
        writestruct(file, f"{pixels_num_bytes}B", *pixels_flat)

        # footer
        writestruct(file, "<2I", 3, 0)


def read_from_png(fp: BinaryFp, pixfmt: Optional[str] = None) -> ImxImage:
    """read from an PNG file and return an ImxImage

    :param fp: A file object or file path to read from. Only PNG images are guaranteed
        to work, but potentially any image format supported by PIL may also work.
    :param pixfmt: pixel format, one of str (rgba32, rgb24, i8, i4), or None for auto
    :raises ValueError if pixfmt isn't valid
    :raises ValueError if file has a pixel mode unsupported by PIL
    :return: ImxImage instance
    """
    with Image.open(fp) as image:

        if pixfmt not in PIXEL_FORMATS and pixfmt is not None:
            raise ValueError(
                f"pixfmt must be one of {PIXEL_FORMATS} or None, was {pixfmt!r}"
            )

        width, height = image.size

        # Choose a pixel format automatically if none is provided
        if pixfmt is None:
            num_colors = image.getcolors()
            num_colors = None if num_colors is None else len(num_colors)

            # If few enough colors for i4, do that (but only if width is even)
            if num_colors is not None and (num_colors <= 16) and (width % 2 == 0):
                pixfmt = "i4"

            # If few enough colors for i8, do that
            elif image.mode in ("P", "L", "1") or (
                num_colors is not None and (num_colors <= 256)
            ):
                pixfmt = "i8"

            # If no alpha, do RGB. All other cases, do RGBA
            else:
                if image.mode not in ("RGBA", "LA", "PA", "RGBa", "La"):
                    # if image is in a mode that doesn't have alpha
                    pixfmt = "rgb24"
                else:
                    if image.mode != "RGBA":
                        image = image.convert("RGBA")
                    no_alpha = all(a == 255 for a in image.getdata(band=3))
                    if no_alpha:
                        pixfmt = "rgb24"
                    else:
                        pixfmt = "rgba32"

        # get pixels and palette, depending on the desired pixel format
        if pixfmt == "rgba32":
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            pixels = image.getdata()
            palette = None
        elif pixfmt == "rgb24":
            if image.mode != "RGB":
                image = image.convert("RGB")
            pixels = image.getdata()
            palette = None
        elif pixfmt in ("i8", "i4"):
            maxcolors = 256 if pixfmt == "i8" else 16
            imagename = getimagename(fp)
            pixels, palette = image2indexed(image, maxcolors, imagename)

    return ImxImage(width, height, pixels, palette, pixfmt, alpha128=False)


def getimagename(file_or_path: BinaryFp) -> str:
    """return the base filename from file_or_path

    :param file_or_path: an open file object, string file path, or pathlib Path
    :return: basename (i.e just filename) of the path (or of the file's path)
    """
    if hasattr(file_or_path, "name"):
        name = str(file_or_path.name)
    else:
        name = str(file_or_path)
    return os.path.basename(name)


def image2indexed(
    image: Image, maxcolors: int = 256, imagename: Optional[str] = None
) -> Tuple[SeqIndexed, SeqRGBA]:
    """return (pixels, palette) of image reduced to maxcolors

    Special handling needed here because Pillow's Image.quantize() may reduce colors
    excessively, resulting in poor image quality
    (https://github.com/python-pillow/Pillow/issues/5204)

    :param image: Pillow Image instance
    :param maxcolors: maximum number of colors allowed in the returned palette
    :param imagename: optional name of image, for printing warnings of excessive color
        reduction. If None, do not print any warnings.
    :return: (pixels, palette) where pixels are indices into palette, palette is RGBA
        colors
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    imgcolors = image.getcolors(maxcolors=maxcolors)

    # if colors exceed maxcolors, use Pillow's built-in quantization to reduce colors.
    if imgcolors is None:  # i.e. if getcolors() exceeded maxcolors

        # Sometimes the same image will quantize better from RGB mode than from RGBA
        # (see https://github.com/python-pillow/Pillow/issues/5217)
        # Therefore, convert to RGB before quantization if there is no alpha
        no_alpha = all(a == 255 for a in image.getdata(band=3))
        if no_alpha:
            image = image.convert("RGB")
        image = image.quantize(colors=maxcolors, dither="FLOYDSTEINBERG")

        # warn if there was excessive color reduction (due to a possible Pillow bug)
        num_destcolors = len(image.getcolors(maxcolors=maxcolors))
        if imagename is not None and (num_destcolors < maxcolors):
            my_warn(
                f"WARNING: {imagename} reduced to {num_destcolors} colors instead of "
                f"{maxcolors} (due to a possible Pillow bug). To avoid this, manually "
                f"reduce your image to {maxcolors} or fewer colors before converting."
            )
        image = image.convert("RGBA")
        imgcolors = image.getcolors(maxcolors=maxcolors)

    # now that colors are reduced sufficiently, do manual pixel/palette extraction
    # (palette is sorted from most to least used colors)
    palette = [color for count, color in sorted(imgcolors, reverse=True)]
    color2pixel = {color: idx for idx, color in enumerate(palette)}
    pixels = [color2pixel[color] for color in image.getdata()]
    return pixels, palette


def write_to_png(imximage: ImxImage, fp: BinaryFp) -> None:
    """write an ImxImage to PNG image file

    :param imximage: an ImxImage instance
    :param fp: A file path or an already-opened file
    """
    if imximage.haspalette:
        image = Image.new("RGBA", imximage.size)
        imx_palette = imximage.palette255
        imx_pixels_rgba = [imx_palette[i] for i in imximage.pixels]
        image.putdata(imx_pixels_rgba)
    elif imximage.hasalpha:
        image = Image.new("RGBA", imximage.size)
        image.putdata(imximage.pixels255)
    else:
        image = Image.new("RGB", imximage.size)
        image.putdata(imximage.pixels255)

    image.save(fp, format="png")


def fast_imx_pixfmt(file_or_data: Union[AnyStr, BinaryIO, bytes]) -> str:
    """return the pixel format of this IMX file/data

    Finds the pixel format quickly without parsing the whole file

    :param file_or_data: Either:
        - an open file object. Current position is assumed to be the beginning of the
        IMX data, and it will be restored before returning; or
        - a bytes object containing IMX file data
    :return: str pixel format, one of: i4, i8, rgb24, rgba32
    """
    if (
        hasattr(file_or_data, "seek")
        and hasattr(file_or_data, "tell")
        and hasattr(file_or_data, "read")
    ):
        # it's a file
        file = file_or_data
        original_pos = file.tell()
        file.seek(0x1C, SEEK_CUR)
        pixfmtdata = file.read(8)
        file.seek(original_pos)

    else:
        # assume it's bytes
        data = file_or_data
        pixfmtdata = data[0x1C:0x24]

    pixfmt = _pixfmtdata_pixfmt.get(pixfmtdata)
    if pixfmt is None:
        raise ImxImageError(f"Unknown IMX pixel format data {pixfmtdata!r}")
    return pixfmt
