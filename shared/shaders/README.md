# Shared shaders

The shader presets every module of this repository has built in. Each build
script copies this folder (without `tools/`) to `romfs:/shaders/`, and each
module lists the presets of `tools/builtin_shaders.inc` under **Shaders >
Built-in shaders**. A preset added here, and to that list, is in every module.

| Preset | From |
|---|---|
| `xbrz`, `eagle`, `crt-easymode` | the tico modules |
| `scanlines` | YabaSanshiro's "Scanline" video filter |
| `blargg-ntsc/snes-*` (Composite, RF, S-Video, RGB, Monochrome) | Snes9x's "Blargg NTSC Filter" (snes_ntsc) |
| `blargg-ntsc/nes-*` (Composite, S-Video, RGB, Monochrome) | FCEUmm's "NTSC Filter" (nes_ntsc) |
| `blargg-ntsc/md-*` (Composite, S-Video, RGB, Monochrome) | Genesis Plus GX's "NTSC Filter", Mega Drive (md_ntsc) |
| `blargg-ntsc/sms-*` (Composite, S-Video, RGB, Monochrome) | Genesis Plus GX's "NTSC Filter", Master System (sms_ntsc) |

Modules: PlayStation (the repository's root), `cores/snes`, `cores/nes`,
`cores/megadrive` and `cores/n64`. `cores/saturn` (YabaSanshiro) has no slang
shader chain and does not use this folder.

## Blargg NTSC

`tools/blargg_ntsc.py` is a port of the part of Shay Green's libraries that
builds their kernels (LGPL 2.1 or later, as the libraries are). It writes
`blargg-ntsc/`: one kernel pass and one preset per library and setting, the
four `<library>.slang` picture passes over `blargg-ntsc.inc`, and
`tools/blargg_ntsc_builtin.inc`. Change the script and run it again rather
than the files it writes:

    python3 shared/shaders/tools/blargg_ntsc.py

The filters work on the console's own pixels. `frame-scale.inc` takes the
internal resolution scale from the size of the frame (lines: the whole
division of the height nearest 240; 200 to 448 pixels a line); the
"Internal resolution scale" parameter of a preset sets it by hand when that
guess is wrong.

Differences from the libraries: the input is the frame's RGB, so NES colours
go through nes_ntsc's RGB palette path and not its own decoding of the PPU's
signal levels; and the picture keeps its place and width, where the libraries
widen it and leave a border.
