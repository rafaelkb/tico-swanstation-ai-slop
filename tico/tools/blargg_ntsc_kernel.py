#!/usr/bin/env python3
"""The kernel table of the Blargg NTSC shader (tico/shaders/blargg-ntsc*).

Snes9x's Blargg NTSC filter is snes_ntsc 0.2.2 (Shay Green, LGPL 2.1+): for
every SNES colour it tabulates how one pixel of that colour spreads over 14
output samples, for each of the three places a pixel can sit against the
colour carrier and each of the three burst phases a line can have, and a
frame is the sum of its pixels' tables. Those tables are linear in the
colour once its gamma is applied, so three of them (red, green and blue)
give every colour, and that is what the shader's first pass holds.

This is snes_ntsc's snes_ntsc_init() and what it calls, in floating point
and without the rounding its packed integers need, for the composite preset
(Snes9x's "Composite": every setting 0, fields merged). Run it to write the
table again:

    python3 tico/tools/blargg_ntsc_kernel.py
"""

from __future__ import annotations

import math
from pathlib import Path

SHADERS = Path(__file__).resolve().parents[1] / "shaders"

# snes_ntsc.c
ALIGNMENTS = 3   # places a pixel can sit: 3 pixels are 8 composite samples
BURSTS = 3       # burst phases, one line after the other
RESCALE_IN = 8   # composite samples...
RESCALE_OUT = 7  # ...to output samples
ENTRY_SIZE = 128
BURST_SIZE = ENTRY_SIZE // BURSTS       # 42: a colour's samples for one burst phase
TAPS = BURST_SIZE // ALIGNMENTS         # 14: output samples one pixel spreads over
ARTIFACTS_MID = 1.0
FRINGING_MID = 1.0

# snes_ntsc_impl.h
KERNEL_HALF = 16
KERNEL_SIZE = KERNEL_HALF * 2 + 1
LUMA_CUTOFF = 0.20
DEFAULT_DECODER = (0.956, 0.621, -0.272, -0.647, -1.105, 1.702)
RGB_TO_YIQ = ((0.299, 0.587, 0.114), (0.596, -0.275, -0.321), (0.212, -0.523, 0.311))

# snes_ntsc_setup_t, as snes_ntsc_composite has it (the decoder matrix is the
# default one and the hue 0, so the decoder is not turned)
COMPOSITE = {"sharpness": 0.0, "resolution": 0.0, "artifacts": 0.0, "fringing": 0.0, "bleed": 0.0,
             "merge_fields": True}


def pixel_offset(ntsc: int, scaled: int) -> tuple[int, float]:
    """PIXEL_OFFSET: where a pixel's kernel starts, and its carrier sign."""
    ntsc_ = ntsc - int(scaled / RESCALE_OUT) * RESCALE_IN  # C division
    scaled_ = (scaled + RESCALE_OUT * 10) % RESCALE_OUT
    offset = (KERNEL_SIZE // 2 + ntsc_ + (scaled_ != 0) + (RESCALE_OUT - scaled_) % RESCALE_OUT
              + KERNEL_SIZE * 2 * scaled_)
    return offset, 1.0 - ((ntsc + 100) & 2)


# snes_ntsc_pixels: how much of each of four composite samples a pixel covers
PIXELS = (
    (pixel_offset(-4, -9), (1, 1, .6667, 0)),
    (pixel_offset(-2, -7), (.3333, 1, 1, .3333)),
    (pixel_offset(0, -5), (0, .6667, 1, 1)),
)


def init_filters(setup: dict) -> list[float]:
    """The chroma and luma kernels, at each of the 7 output sample offsets."""
    kernels = [0.0] * (KERNEL_SIZE * 2)

    # luma: a sinc with rolloff, under a Blackman window
    rolloff = 1 + setup["sharpness"] * 0.032
    maxh = 32.0
    pow_a_n = rolloff ** maxh
    to_angle = setup["resolution"] + 1
    to_angle = math.pi / maxh * LUMA_CUTOFF * (to_angle * to_angle + 1)
    centre = KERNEL_SIZE * 3 // 2
    kernels[centre] = maxh
    for i in range(KERNEL_HALF * 2 + 1):
        x = i - KERNEL_HALF
        angle = x * to_angle
        if x or pow_a_n > 1.056 or pow_a_n < 0.981:
            rolloff_cos_a = rolloff * math.cos(angle)
            num = (1 - rolloff_cos_a - pow_a_n * math.cos(maxh * angle)
                   + pow_a_n * rolloff * math.cos((maxh - 1) * angle))
            den = 1 - rolloff_cos_a - rolloff_cos_a + rolloff * rolloff
            kernels[centre - KERNEL_HALF + i] = num / den - 0.5
    total = 0.0
    for i in range(KERNEL_HALF * 2 + 1):
        x = math.pi * 2 / (KERNEL_HALF * 2) * i
        kernels[centre - KERNEL_HALF + i] *= 0.42 - 0.5 * math.cos(x) + 0.08 * math.cos(x * 2)
        total += kernels[centre - KERNEL_HALF + i]
    for i in range(KERNEL_HALF * 2 + 1):
        kernels[centre - KERNEL_HALF + i] /= total

    # chroma: a gaussian, its even and odd samples normalized apart
    cutoff_factor = -0.03125
    cutoff = setup["bleed"]
    if cutoff < 0:
        cutoff = cutoff ** 8 * (-30.0 / 0.65)
    cutoff = cutoff_factor - 0.65 * cutoff_factor * cutoff
    for i in range(-KERNEL_HALF, KERNEL_HALF + 1):
        kernels[KERNEL_SIZE // 2 + i] = math.exp(i * i * cutoff)
    for phase in range(2):
        total = sum(kernels[x] for x in range(phase, KERNEL_SIZE, 2))
        for x in range(phase, KERNEL_SIZE, 2):
            kernels[x] /= total

    # 8 composite samples become 7 output samples: linear rescale kernels
    out = []
    weight = 1.0
    for _ in range(RESCALE_OUT):
        remain = 0.0
        weight -= 1.0 / RESCALE_IN
        for cur in kernels:
            m = cur * weight
            out.append(m + remain)
            remain = cur - m
    return out


def decoders() -> list[list[float]]:
    """YIQ to RGB for each burst phase: the decoder turned 120 degrees a phase."""
    s, c = 0.0, 1.0
    out = []
    for _ in range(BURSTS):
        out.append([v for n in range(3)
                    for v in (DEFAULT_DECODER[n * 2] * c - DEFAULT_DECODER[n * 2 + 1] * s,
                              DEFAULT_DECODER[n * 2] * s + DEFAULT_DECODER[n * 2 + 1] * c)])
        s, c = s * -0.5 - c * 0.866025, s * 0.866025 + c * -0.5
    return out


def gen_kernel(setup: dict, kernel: list[float], to_rgb: list[list[float]],
               y: float, i: float, q: float) -> list[tuple[float, ...]]:
    """One colour at every burst phase and alignment: BURSTS * BURST_SIZE samples."""
    artifacts = setup["artifacts"]
    if artifacts > 0:
        artifacts *= ARTIFACTS_MID * 1.5 - ARTIFACTS_MID
    artifacts = artifacts * ARTIFACTS_MID + ARTIFACTS_MID
    fringing = setup["fringing"]
    if fringing > 0:
        fringing *= FRINGING_MID * 2 - FRINGING_MID
    fringing = fringing * FRINGING_MID + FRINGING_MID

    out = []
    for burst in range(BURSTS):
        decoder = to_rgb[burst]
        for (offset, negate), covers in PIXELS:
            # two composite signals, so artifacts and fringing can be set apart
            yy = y * fringing * negate
            ic0 = (i + yy) * covers[0]
            qc1 = (q + yy) * covers[1]
            ic2 = (i - yy) * covers[2]
            qc3 = (q - yy) * covers[3]
            factor = artifacts * negate
            yc0 = (y + i * factor) * covers[0]
            yc2 = (y - i * factor) * covers[2]
            yc1 = (y + q * factor) * covers[1]
            yc3 = (y - q * factor) * covers[3]
            k = offset
            for _ in range(TAPS):
                fi = kernel[k] * ic0 + kernel[k + 2] * ic2
                fq = kernel[k + 1] * qc1 + kernel[k + 3] * qc3
                fy = (kernel[k + KERNEL_SIZE] * yc0 + kernel[k + KERNEL_SIZE + 1] * yc1
                      + kernel[k + KERNEL_SIZE + 2] * yc2 + kernel[k + KERNEL_SIZE + 3] * yc3)
                if k < KERNEL_SIZE * 2 * (RESCALE_OUT - 1):
                    k += KERNEL_SIZE * 2 - 1
                else:
                    k -= KERNEL_SIZE * 2 * (RESCALE_OUT - 1) + 2
                out.append((fy + decoder[0] * fi + decoder[1] * fq,
                            fy + decoder[2] * fi + decoder[3] * fq,
                            fy + decoder[4] * fi + decoder[5] * fq))
        i, q = i * -0.5 - q * -0.866025, i * -0.866025 + q * -0.5  # -120 degrees
    return out


def merge_kernel_fields(entry: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Each burst phase with the next: the two fields of a frame, seen at once."""
    out = list(entry)
    for n in range(BURST_SIZE):
        for burst in range(BURSTS):
            a = entry[BURST_SIZE * burst + n]
            b = entry[BURST_SIZE * ((burst + 1) % BURSTS) + n]
            out[BURST_SIZE * burst + n] = tuple((x + y) / 2 for x, y in zip(a, b))
    return out


def correct_errors(color: tuple[float, ...], entry: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """A plain colour comes out as itself at every output sample."""
    out = [list(sample) for sample in entry]
    for burst in range(BURSTS):
        base = burst * BURST_SIZE
        for i in range(TAPS // 2):
            summed = (i, (i + 12) % 14 + 14, (i + 10) % 14 + 28, i + 7, i + 5 + 14, i + 3 + 28)
            for channel in range(3):
                error = color[channel] - sum(out[base + n][channel] for n in summed)
                fourth = error / 4
                for n in (i + 3 + 28, i + 5 + 14, i + 7):
                    out[base + n][channel] += fourth
                out[base + i][channel] += error - fourth * 3
    return [tuple(sample) for sample in out]


def entry(setup: dict, rgb: tuple[float, float, float]) -> list[tuple[float, ...]]:
    """snes_ntsc_init's table entry for a colour (after its gamma)."""
    kernel = init_filters(setup)
    to_rgb = decoders()
    y, i, q = (sum(row[n] * rgb[n] for n in range(3)) for row in RGB_TO_YIQ)
    decoder = to_rgb[0]
    color = (y + decoder[0] * i + decoder[1] * q, y + decoder[2] * i + decoder[3] * q,
             y + decoder[4] * i + decoder[5] * q)
    out = gen_kernel(setup, kernel, to_rgb, y, i, q)
    if setup["merge_fields"]:
        out = merge_kernel_fields(out)
    return correct_errors(color, out)


def table(setup: dict) -> list[list[tuple[float, ...]]]:
    """The shader's rows: per burst phase, alignment and input channel, 14 taps.

    The alignment is the pixel's place in snes_ntsc's chunk of three (the
    blitter's kernel0, kernel1 and kernel2); its tap 0 falls on output sample
    0, 2 and 4 of that chunk.
    """
    primaries = [entry(setup, rgb) for rgb in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    return [primaries[channel][burst * BURST_SIZE + alignment * TAPS:][:TAPS]
            for burst in range(BURSTS) for alignment in range(ALIGNMENTS) for channel in range(3)]


HEADER = """#version 450

/*
   Blargg's NTSC filter: the kernel table for the %(name)s preset.

   Written by tico/tools/blargg_ntsc_kernel.py from snes_ntsc 0.2.2, the
   filter Snes9x uses. Copyright (C) 2006-2007 Shay Green, GNU Lesser General
   Public License, version 2.1 or later.

   One row per burst phase (3), place of the pixel against the colour
   carrier (3) and input channel (red, green, blue): what a pixel with that
   channel at 1 adds to the 14 output samples it spreads over. A column of
   zeroes either side lets blargg-ntsc.slang read between samples.
*/

layout(push_constant) uniform Push
{
    vec4 OutputSize;
} params;

layout(std140, set = 0, binding = 0) uniform UBO
{
    mat4 MVP;
} global;

#pragma stage vertex
layout(location = 0) in vec4 Position;
layout(location = 1) in vec2 TexCoord;
layout(location = 0) out vec2 vTexCoord;

void main()
{
    gl_Position = global.MVP * Position;
    vTexCoord = TexCoord;
}

#pragma stage fragment
#pragma format R16G16B16A16_SFLOAT
layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 FragColor;

const int kTaps = %(taps)d;
const int kRows = %(rows)d;

const vec3 kKernel[kRows * kTaps] = vec3[kRows * kTaps](
"""

FOOTER = """);

void main()
{
    ivec2 texel = ivec2(floor(vTexCoord * params.OutputSize.xy));
    int tap = texel.x - 1;
    vec3 k = vec3(0.0);
    if (tap >= 0 && tap < kTaps && texel.y >= 0 && texel.y < kRows)
        k = kKernel[texel.y * kTaps + tap];
    FragColor = vec4(k, 1.0);
}
"""


def write(name: str, setup: dict) -> Path:
    rows = table(setup)
    lines = []
    for index, row in enumerate(rows):
        burst, rest = divmod(index, ALIGNMENTS * 3)
        lines.append(f"    // burst {burst}, pixel {rest // 3}, {'red green blue'.split()[rest % 3]}")
        for tap in row:
            lines.append("    vec3(" + ", ".join(f"{v:.6f}" for v in tap) + "),")
    lines[-1] = lines[-1].rstrip(",")
    path = SHADERS / f"blargg-ntsc-{name.lower()}-kernel.slang"
    path.write_text(HEADER % {"name": name, "taps": TAPS, "rows": len(rows)} + "\n".join(lines) + "\n"
                    + FOOTER)
    return path


if __name__ == "__main__":
    print("wrote", write("Composite", COMPOSITE).relative_to(SHADERS.parents[1]))
