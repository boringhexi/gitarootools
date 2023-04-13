# Changelog

0.1.7:
- (gm-pakunpack) fix gm-pakunpack not working

0.1.6:
- (gm-gmo2animnames) add tool gmo2animnames to extract animation names from GMO models
- (gm-pakpack/pakunpack) add tools gm-pakpack/pakunpack for Gitaroo Man Lives! PAK files
- Support for Python 3.10 and 3.11

0.1.5:
- (gm-png2imx) regarding color quantization (converting to a 256- or 16-color image) and
  [Pillow issue #5204](https://github.com/python-pillow/Pillow/issues/5204) (where
  quantization reduces colors too much in some cases, usually affecting images that have
  transparency):
  - A warning will be printed if an image is negatively impacted by  Pillow issue #5204.
  - An input image that already has few enough colors (256/16 or fewer) will no longer
    be impacted by Pillow issue #5204.
- drop support for Python 3.6

0.1.4:
- now works with Python 3.9

0.1.3:
- (gm-imx2png/png2imx) add tools gm-imx2png/png2imx

0.1.2:
- (gm-xgmpack/unpack) add tools gm-xgmpack/unpack
- (all IMC/subsong tools) simplify help text
- (gm-imcunpack) change names of created directories (e.g. TITLE_IMC instead of TITLE)

0.1.1:
- (IMC audio tests) use public domain audio 
- (gm-subsong2subimc/wav, gm-subsongconv) allow sample rates as low as 8000 (note: below
  22050 has not been tested on real PS2)
- (gm-imcpack/unpack) add new channel replacement syntax for IMC.toml files (old
  way still works but is no longer documented)

0.1.0:
 - initial release
