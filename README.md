# gitarootools — command line tools to work with Gitaroo Man game data
 
*Gitaroo Man* is a rhythm action video game for PlayStation 2. This set of tools allows
you to work with data from the game, converting game files to more viewable formats. In
some cases, files converted this way can be edited, converted back to a game format, and
reinserted into the game.

## Installation
The easiest way to install `gitarootools` is to use `pip`:
```bash
pip install gitarootools
```

## Usage
See each tool's help and usage by running
```bash
gm-<toolname> -h
```

## Included tools
### Archive

**`gm-xgmpack`**: pack files into an XGM container

**`gm-xgmunpack`**: unpack files from an XGM container

### Audio

**`gm-imcpack`**: pack subsongs into an IMC audio container

**`gm-imcunpack`**: unpack subsongs from an IMC audio container

**`gm-subsongconv`**: convert a subsong to another format

**`gm-subsong2[subimc|wav]`**: convert multiple subsongs to the specified format

### Image

**`gm-imx2png`**: convert IMX images to PNG

**`gm-png2imx`**: convert PNG images to IMX

## Resources
* [Gitaroo Pals](https://discord.gg/ed6P8Jt) Discord server for help and support
* [Issue Tracker](https://github.com/boringhexi/gitarootools/issues)