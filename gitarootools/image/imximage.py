# -*- coding: utf-8 -*-
#  Copyright (c) 2019, 2020 boringhexi
"""imximage.py - read/write IMX image files

An IMX image file is a file type from Gitaroo Man that has the extension .IMX
and contains RGB(A) or indexed image data."""
from itertools import chain, repeat
from os import SEEK_CUR
from typing import AnyStr, BinaryIO, Optional, Sequence, Tuple, Union

from PIL import Image

from gitarootools.miscutils.datautils import (
    chunks,
    from_nibbles,
    open_maybe,
    readdata,
    readstruct,
    to_nibbles,
    writestruct,
    zip_to_1st,
)

SeqIndexed = Sequence[int]
SeqRGB = Sequence[Tuple[int, int, int]]
SeqRGBA = Sequence[Tuple[int, int, int, int]]

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

        if alpha128:  # use alpha as-is
            self._pixels = pixels
            self._palette = palette

        else:  # convert alpha255 to alpha128
            if palette is not None:  # convert palette alpha
                # alpha128 = ceil(alpha255/255*128)
                self._palette = [
                    (r, g, b, int(a / 255 * 128 + 0.5)) for (r, g, b, a) in palette
                ]
                self._pixels = pixels
            elif pixels and len(pixels[0]) == 4:  # convert RGBA alpha
                self._palette = palette
                # alpha128 = ceil(alpha255/255*128)
                self._pixels = [
                    (r, g, b, int(a / 255 * 128 + 0.5)) for (r, g, b, a) in pixels
                ]
            else:  # RGB has no alpha
                self._palette = palette
                self._pixels = pixels

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
    def palette(self) -> SeqRGBA:
        """palette, alpha values are 128-based"""
        return self._palette

    @property
    def pixels(self) -> Union[SeqRGB, SeqRGBA, SeqIndexed]:
        """pixels, alpha values are 128-based"""
        return self._pixels

    def export_palette_rgb_flat(self) -> Optional[SeqRGB]:
        """return palette RGB as a flat list, for use in exporting to an image format

        Only returns RGB components, concatenated as a flat list. For alpha, use
        ImxImage.export_palette_alpha_bytes()

        :return None if no palette, or sequence of (r,g,b) colors
        """
        palette = self._palette
        if palette is not None:
            return tuple(chain.from_iterable(col[:3] for col in palette))
        else:
            return None

    def export_palette_alpha_bytes(self) -> Optional[bytes]:
        """return palette alpha as bytes, for use in exporting to an image format

        :return: None if no palette, or bytes of palette entries' alpha
        """
        palette = self._palette
        if palette is None:
            return None
        # convert alpha: alpha255 = floor(alpha128/128*255)
        alphas255 = (int(col[3] / 128 * 255) for col in palette)
        # occasional super-opaque values need to be clamped to 255
        return bytes(a if a <= 255 else 255 for a in alphas255)

    def export_pixels(self) -> Union[SeqRGB, SeqRGBA, SeqIndexed]:
        """return pixels for use in exporting to an image format

        :return Sequence of indices into the palette if there is a palette, or
            sequence of (r,g,b) or (r,g,b,a) colors. For rgba, alpha values will have
            been converted from 128-based alpha to 255-based alpha
        """
        pixels = self._pixels
        if not pixels:
            return []
        if self._palette is None and len(pixels[0]) == 4:  # convert RGBA alpha
            # convert alpha: floor(alpha128/128*255)
            return [(r, g, b, int(a / 128 * 255)) for (r, g, b, a) in pixels]
        else:  # don't convert indexed pixels or RGB
            return pixels


def read_imx(file) -> ImxImage:
    """read from an IMX image file and return an ImxImage

    :param file: A file path. Or it can be an already-opened file, in which case:
        - it will read starting from the current file position
        - after returning, file position will be right after the IMX file data
        - the caller is responsible for closing the file afterwards
    :raises ImxImageError if IMX header is invalid
    :raises EndOfImxImageError if end of IMX data is reached unexpectedly
    :return: ImxImage instance
    """
    with open_maybe(file, "rb") as file:
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


def write_imx(imximage: ImxImage, file: Union[BinaryIO, AnyStr]) -> None:
    """write imximage to file

    :param imximage: an ImxImage instance
    :param file: A file path. Or it can be an already-opened file, in which case:
        - it will write starting from the current file position
        - after returning, file position will be right after the written IMX data
        - the caller is responsible for closing the file afterwards
    """
    with open_maybe(file, "wb") as file:
        # header
        file.write(b"IMX\0")
        pixfmtdata = _pixfmt_pixfmtdata[imximage.pixfmt]
        writestruct(file, "<16x2I8s", *imximage.size, pixfmtdata)

        # palette
        if imximage.pixfmt in ("i4", "i8"):
            palette = imximage.palette
            palette_num_bytes = len(palette) * 4
            writestruct(file, "<I", palette_num_bytes)
            writestruct(file, f"{palette_num_bytes}B", *chain.from_iterable(palette))
            writestruct(file, "<I", 2)

        # pixels
        pixels = imximage.pixels
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


def read_from_png(
    file: Union[BinaryIO, AnyStr], pixfmt: Optional[str] = None
) -> ImxImage:
    """read from an PNG file and return an ImxImage

    :param file: A file object or file path to read from. Only PNG images are guaranteed
        to work, but potentially any image format supported by PIL may also work.
    :param pixfmt: pixel format, one of str (rgba32, rgb24, i8, i4), or None for auto
    :raises ValueError if pixfmt isn't valid
    :raises ValueError if file has a pixel mode unsupported by PIL
    :return: ImxImage instance
    """
    with Image.open(file) as image:

        if pixfmt not in PIXEL_FORMATS and pixfmt is not None:
            raise ValueError(
                f"pixfmt must be one of {PIXEL_FORMATS} or None, was {pixfmt!r}"
            )
        if image.mode not in ("RGB", "RGBA", "P"):
            raise ValueError(f"Image mode {image.mode!r} is not supported yet")

        width, height = image.size

        # Choose a pixel format automatically
        if pixfmt is None:
            # potentially convert RGBA to RGB, if lossless
            if image.mode == "RGBA":
                image_rgb = image.convert("RGB")
                is_rgb = tuple(image_rgb.convert("RGBA").getdata()) == tuple(
                    image.getdata()
                )
                if is_rgb:
                    image = image_rgb

            # potentially convert RGB/RGBA to indexed, if lossless
            num_colors = len(set(image.getdata()))
            if image.mode in ("RGBA", "RGB"):
                if num_colors <= 256:
                    image = image.quantize(colors=num_colors)

            # determine pixel format
            if image.mode == "RGBA":
                pixfmt = "rgba32"
            elif image.mode == "RGB":
                pixfmt = "rgb24"
            elif image.mode == "P" and (num_colors <= 16 and width % 2 == 0):
                pixfmt = "i4"
            elif image.mode == "P" and num_colors <= 256:
                pixfmt = "i8"
            else:
                raise ValueError(
                    "Could not automatically choose pixel format, "
                    f"image.mode={image.mode!r}, num_colors={num_colors!r}"
                )

        # get pixels and palette, depending on the desired pixel format
        if pixfmt == "rgba32":
            image = image.convert("RGBA")
            pixels = tuple(image.getdata())
            palette = None
        elif pixfmt == "rgb24":
            image = image.convert("RGB")
            pixels = tuple(image.getdata())
            palette = None
        elif pixfmt in ("i8", "i4"):

            # Quantize RGB/RGBA image to the right number of colors.
            # (Do not quantize a "P" (palette) image, convert to "RGBA" first!)
            if image.mode != "P":
                image = image.quantize(
                    colors=(256 if pixfmt == "i8" else 16), dither="FLOYDSTEINBERG"
                )
            # If palette image destined for i4 has more than 16 colors, quantize to 16
            elif pixfmt == "i4" and len(set(image.getdata())) > 16:
                image = image.convert("RGBA").quantize(
                    colors=16, dither="FLOYDSTEINBERG"
                )

            pixels = tuple(image.getdata())

            # Get palette:
            # 1. get palette alpha from the transparency info. One of 3 possible types:
            # - iterable of int alpha values corresponding to the palette's rgb values.
            #   if it's shorter than the palette, rest of the palette is opaque
            # - single int, the index of the fully transparent palette color
            # - not present, in which case the entire palette is opaque
            transparency_info = image.info.get("transparency")
            if transparency_info is None:
                # opaque, will be filled in with all 255
                im_palette_alpha = ()
            elif not hasattr(transparency_info, "__iter__"):
                # only one transparent, all the rest is opaque 255
                transp_idx = transparency_info
                im_palette_alpha = chain(repeat(255, transp_idx), (0,))
            else:
                im_palette_alpha = transparency_info
            # 2. zip together palette rgb and alpha. If palette alpha is too short, fill
            # the rest in with 255
            im_palette_rgb = chunks(image.getpalette(), 3)
            palette = tuple(
                (r, g, b, a)
                for (r, g, b), a in zip_to_1st(
                    im_palette_rgb, im_palette_alpha, fillvalue=255
                )
            )

            # Now we have pixels and palette. If the image is destined for i4, it
            # already has just 16 colors. But it's likely the palette contains too many
            # unused entries, so consolidate palette and redo pixels to match.
            if pixfmt == "i4" and len(palette) > 16:
                old_palette = palette
                old_pixels = pixels

                # 1. create new palette containing only used colors,
                # and keep track of how to get from an old palette index to a new one
                used_paletteidxs = set(pixels)
                new_palette = []
                map_old_new_paletteidxs = dict()
                newidx = 0
                for oldidx, oldcol in enumerate(old_palette):
                    if oldidx in used_paletteidxs:
                        new_palette.append(oldcol)
                        map_old_new_paletteidxs[oldidx] = newidx
                        newidx += 1
                # 2. redo pixels -- replicate the old pixels using the new palette
                new_pixels = [map_old_new_paletteidxs[old] for old in old_pixels]
                # 3. pad palette to 16 colors
                new_palette = tuple(
                    chain(new_palette, ((0, 0, 0, 0),) * (16 - len(new_palette)))
                )

                pixels, palette, = new_pixels, new_palette

    return ImxImage(width, height, pixels, palette, pixfmt, alpha128=False)


def write_to_png(imximage: ImxImage, file: Union[BinaryIO, AnyStr]) -> None:
    """write an ImxImage to PNG image file

    :param imximage: an ImxImage instance
    :param file: A file path or an already-opened file
    """
    if imximage.haspalette:
        image = Image.new("P", imximage.size)
        image.putpalette(imximage.export_palette_rgb_flat())
        image.info["transparency"] = imximage.export_palette_alpha_bytes()
    elif imximage.hasalpha:
        image = Image.new("RGBA", imximage.size)
    else:
        image = Image.new("RGB", imximage.size)
    image.putdata(imximage.export_pixels())

    image.save(file, format="png")


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
