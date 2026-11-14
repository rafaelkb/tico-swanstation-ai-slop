#!/usr/bin/env python3
"""The kernel tables of the Blargg NTSC shaders (shared/shaders/blargg-ntsc/).

Blargg's NTSC filters (Shay Green, LGPL 2.1+) are what four of the cores
have as their TV filter: snes_ntsc in Snes9x, nes_ntsc in FCEUmm, and
md_ntsc and sms_ntsc in Genesis Plus GX. They are one algorithm with
different constants. For every colour of the console it tabulates how one
pixel of that colour spreads over 14 or 16 output samples, for each place a
pixel can sit against the colour carrier and each burst phase a line can
have, and a frame is the sum of its pixels' tables. Those tables are linear
in the colour once its gamma is applied, so three of them (red, green and
blue) give every colour, and that is what the first pass of a preset holds.

This is the libraries' *_ntsc_init() and what it calls (*_ntsc_impl.h), in
floating point and without the rounding their packed integers need, for the
presets the cores offer. Run it to write the shaders again:

    python3 shared/shaders/tools/blargg_ntsc.py
"""

from __future__ import annotations

import math
from pathlib import Path

SHADERS = Path(__file__).resolve().parents[1]

# *_ntsc_impl.h
KERNEL_HALF = 16
KERNEL_SIZE = KERNEL_HALF * 2 + 1
DEFAULT_DECODER = (0.956, 0.621, -0.272, -0.647, -1.105, 1.702)
RGB_TO_YIQ = ((0.299, 0.587, 0.114), (0.596, -0.275, -0.321), (0.212, -0.523, 0.311))

# Three pixels over eight composite samples (snes, nes, sms), and two over
# four (md): how much of each of four samples a pixel covers.
PIXELS_3 = (((-4, -9), (1, 1, .6667, 0)), ((-2, -7), (.3333, 1, 1, .3333)), ((0, -5), (0, .6667, 1, 1)))
PIXELS_2 = (((-4, -9), (.1, .9, .9, .1)), ((-2, -7), (.1, .9, .9, .1)))


def setup(saturation=0.0, sharpness=0.0, resolution=0.0, artifacts=0.0, fringing=0.0, bleed=0.0,
          merge_fields=False) -> dict:
    """A *_ntsc_setup_t; hue, contrast, brightness and gamma are 0 in every preset."""
    return dict(saturation=saturation, sharpness=sharpness, resolution=resolution, artifacts=artifacts,
                fringing=fringing, bleed=bleed, merge_fields=merge_fields)


# The constants each library is built with (the top of its .c), how its
# emulator steps the burst phase, and the presets its core option offers.
FAMILIES = {
    "snes": dict(
        title="SNES", library="snes_ntsc 0.2.2", emulator="Snes9x",
        alignments=3, bursts=3, taps=14, rescale_in=8, rescale_out=7, pixels=PIXELS_3,
        artifacts_mid=1.0, artifacts_max=1.5, fringing_mid=1.0, fringing_max=2.0, luma_cutoff=0.20,
        gamma=1.1333, errors="distribute", frame_phases=3,
        presets=(
            ("composite", "Composite", setup(merge_fields=True)),
            ("rf", "RF", setup(merge_fields=False)),
            ("svideo", "S-Video", setup(sharpness=.2, resolution=.2, artifacts=-1, fringing=-1, merge_fields=True)),
            ("rgb", "RGB", setup(sharpness=.2, resolution=.7, artifacts=-1, fringing=-1, bleed=-1, merge_fields=True)),
            ("monochrome", "Monochrome", setup(saturation=-1, sharpness=.2, resolution=.2, artifacts=-.2,
                                               fringing=-.2, bleed=-1, merge_fields=True)),
        )),
    # FCEUmm never merges the fields, and steps the burst phase between two
    # values. The palette it hands nes_ntsc is RGB, which takes no gamma.
    "nes": dict(
        title="NES", library="nes_ntsc 0.2.2", emulator="FCEUmm",
        alignments=3, bursts=3, taps=14, rescale_in=8, rescale_out=7, pixels=PIXELS_3,
        artifacts_mid=1.0, artifacts_max=1.5, fringing_mid=1.0, fringing_max=2.0, luma_cutoff=0.20,
        gamma=1.0, errors="distribute", frame_phases=2,
        presets=(
            ("composite", "Composite", setup()),
            ("svideo", "S-Video", setup(sharpness=.2, resolution=.2, artifacts=-1, fringing=-1)),
            ("rgb", "RGB", setup(sharpness=.2, resolution=.7, artifacts=-1, fringing=-1, bleed=-1)),
            ("monochrome", "Monochrome", setup(saturation=-1, sharpness=.2, resolution=.2, artifacts=-.2,
                                               fringing=-.2, bleed=-1)),
        )),
    "md": dict(
        title="Mega Drive", library="md_ntsc 0.1.2", emulator="Genesis Plus GX",
        alignments=2, bursts=1, taps=16, rescale_in=1, rescale_out=1, pixels=PIXELS_2,
        artifacts_mid=0.40, artifacts_max=1.00, fringing_mid=0.30, fringing_max=0.60, luma_cutoff=0.1974,
        gamma=1.1333, errors="md", frame_phases=1,
        presets=(
            ("composite", "Composite", setup()),
            ("svideo", "S-Video", setup(resolution=.2, artifacts=-1, fringing=-1)),
            ("rgb", "RGB", setup(sharpness=.2, resolution=.7, artifacts=-1, fringing=-1, bleed=-1)),
            ("monochrome", "Monochrome", setup(saturation=-1, sharpness=.2, artifacts=-.2, fringing=-.2, bleed=-1)),
        )),
    "sms": dict(
        title="Master System", library="sms_ntsc 0.2.3", emulator="Genesis Plus GX",
        alignments=3, bursts=1, taps=14, rescale_in=8, rescale_out=7, pixels=PIXELS_3,
        artifacts_mid=0.4, artifacts_max=1.2, fringing_mid=0.8, fringing_max=1.6, luma_cutoff=0.20,
        gamma=1.1333, errors="single", frame_phases=1,
        presets=(
            ("composite", "Composite", setup(resolution=.25)),
            ("svideo", "S-Video", setup(resolution=.25, artifacts=-1, fringing=-1)),
            ("rgb", "RGB", setup(sharpness=.2, resolution=.70, artifacts=-1, fringing=-1, bleed=-1)),
            ("monochrome", "Monochrome", setup(saturation=-1, sharpness=.2, resolution=.2, artifacts=-.2,
                                               fringing=-.2, bleed=-1)),
        )),
}


def pixel_offset(fam: dict, ntsc: int, scaled: int) -> tuple[int, float]:
    """PIXEL_OFFSET: where a pixel's kernel starts, and its carrier sign."""
    negate = 1.0 - ((ntsc + 100) & 2)
    out, in_ = fam["rescale_out"], fam["rescale_in"]
    if in_ <= 1:
        return KERNEL_SIZE // 2 + ntsc - scaled, negate
    ntsc_ = ntsc - int(scaled / out) * in_  # C division
    scaled_ = (scaled + out * 10) % out
    return (KERNEL_SIZE // 2 + ntsc_ + (scaled_ != 0) + (out - scaled_) % out + KERNEL_SIZE * 2 * scaled_), negate


def init_filters(fam: dict, setup: dict) -> list[float]:
    """The chroma and luma kernels, at each output sample offset."""
    kernels = [0.0] * (KERNEL_SIZE * 2)

    # luma: a sinc with rolloff, under a Blackman window
    rolloff = 1 + setup["sharpness"] * 0.032
    maxh = 32.0
    pow_a_n = rolloff ** maxh
    to_angle = setup["resolution"] + 1
    to_angle = math.pi / maxh * fam["luma_cutoff"] * (to_angle * to_angle + 1)
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

    if fam["rescale_out"] <= 1:
        return kernels
    # 8 composite samples become 7 output samples: linear rescale kernels
    out = []
    weight = 1.0
    for _ in range(fam["rescale_out"]):
        remain = 0.0
        weight -= 1.0 / fam["rescale_in"]
        for cur in kernels:
            m = cur * weight
            out.append(m + remain)
            remain = cur - m
    return out


def decoders(fam: dict, setup: dict) -> list[list[float]]:
    """YIQ to RGB for each burst phase: the decoder turned 120 degrees a phase."""
    sat = setup["saturation"] + 1
    s, c = 0.0, sat  # the hue is 0 in every preset
    out = []
    for _ in range(fam["bursts"]):
        out.append([v for n in range(3)
                    for v in (DEFAULT_DECODER[n * 2] * c - DEFAULT_DECODER[n * 2 + 1] * s,
                              DEFAULT_DECODER[n * 2] * s + DEFAULT_DECODER[n * 2 + 1] * c)])
        s, c = s * -0.5 - c * 0.866025, s * 0.866025 + c * -0.5
    return out


def gen_kernel(fam: dict, setup: dict, kernel: list[float], to_rgb: list[list[float]],
               y: float, i: float, q: float) -> list[tuple[float, ...]]:
    """One colour at every burst phase and alignment: bursts * alignments * taps samples."""
    artifacts = setup["artifacts"]
    if artifacts > 0:
        artifacts *= fam["artifacts_max"] - fam["artifacts_mid"]
    artifacts = artifacts * fam["artifacts_mid"] + fam["artifacts_mid"]
    fringing = setup["fringing"]
    if fringing > 0:
        fringing *= fam["fringing_max"] - fam["fringing_mid"]
    fringing = fringing * fam["fringing_mid"] + fam["fringing_mid"]
    rescale_out = fam["rescale_out"]

    out = []
    for burst in range(fam["bursts"]):
        decoder = to_rgb[burst]
        for (ntsc, scaled), covers in fam["pixels"]:
            offset, negate = pixel_offset(fam, ntsc, scaled)
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
            for _ in range(fam["taps"]):
                fi = kernel[k] * ic0 + kernel[k + 2] * ic2
                fq = kernel[k + 1] * qc1 + kernel[k + 3] * qc3
                fy = (kernel[k + KERNEL_SIZE] * yc0 + kernel[k + KERNEL_SIZE + 1] * yc1
                      + kernel[k + KERNEL_SIZE + 2] * yc2 + kernel[k + KERNEL_SIZE + 3] * yc3)
                if rescale_out <= 1:
                    k -= 1
                elif k < KERNEL_SIZE * 2 * (rescale_out - 1):
                    k += KERNEL_SIZE * 2 - 1
                else:
                    k -= KERNEL_SIZE * 2 * (rescale_out - 1) + 2
                out.append((fy + decoder[0] * fi + decoder[1] * fq,
                            fy + decoder[2] * fi + decoder[3] * fq,
                            fy + decoder[4] * fi + decoder[5] * fq))
        i, q = i * -0.5 - q * -0.866025, i * -0.866025 + q * -0.5  # -120 degrees
    return out


def merge_kernel_fields(fam: dict, entry: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Each burst phase with the next: the two fields of a frame, seen at once."""
    size = fam["alignments"] * fam["taps"]
    out = list(entry)
    for n in range(size):
        for burst in range(fam["bursts"]):
            a = entry[size * burst + n]
            b = entry[size * ((burst + 1) % fam["bursts"]) + n]
            out[size * burst + n] = tuple((x + y) / 2 for x, y in zip(a, b))
    return out


def correct_errors(fam: dict, color: tuple[float, ...], entry: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """A plain colour comes out as itself at every output sample."""
    out = [list(sample) for sample in entry]
    for burst in range(fam["bursts"]):
        base = burst * fam["alignments"] * fam["taps"]
        if fam["errors"] == "md":
            for i in range(fam["taps"] // 4):
                summed = (i, i + 2 + 16, i + 4, i + 6 + 16, i + 8, (i + 10) % 16 + 16, (i + 12) % 16,
                          (i + 14) % 16 + 16)
                for channel in range(3):
                    out[base + i + 6 + 16][channel] += color[channel] - sum(out[base + n][channel] for n in summed)
            continue
        for i in range(fam["taps"] // 2):
            summed = (i, (i + 12) % 14 + 14, (i + 10) % 14 + 28, i + 7, i + 5 + 14, i + 3 + 28)
            for channel in range(3):
                error = color[channel] - sum(out[base + n][channel] for n in summed)
                if fam["errors"] == "single":
                    out[base + i + 3 + 28][channel] += error
                    continue
                fourth = error / 4
                for n in (i + 3 + 28, i + 5 + 14, i + 7):
                    out[base + n][channel] += fourth
                out[base + i][channel] += error - fourth * 3
    return [tuple(sample) for sample in out]


def entry(fam: dict, setup: dict, rgb: tuple[float, float, float]) -> list[tuple[float, ...]]:
    """The library's table entry for a colour (after its gamma)."""
    kernel = init_filters(fam, setup)
    to_rgb = decoders(fam, setup)
    y, i, q = (sum(row[n] * rgb[n] for n in range(3)) for row in RGB_TO_YIQ)
    decoder = to_rgb[0]
    color = (y + decoder[0] * i + decoder[1] * q, y + decoder[2] * i + decoder[3] * q,
             y + decoder[4] * i + decoder[5] * q)
    out = gen_kernel(fam, setup, kernel, to_rgb, y, i, q)
    # the libraries merge the fields themselves once a preset has no artifacts
    if fam["bursts"] > 1 and (setup["merge_fields"] or (setup["artifacts"] <= -1 and setup["fringing"] <= -1)):
        out = merge_kernel_fields(fam, out)
    return correct_errors(fam, color, out)


def table(fam: dict, setup: dict) -> list[list[tuple[float, ...]]]:
    """The shader's rows: per burst phase, alignment and input channel, the taps.

    The alignment is the pixel's place against the carrier: the blitter's
    kernel0, kernel1 and kernel2 (snes, nes, sms) or the even and odd pixels
    (md). Its tap 0 falls two output samples after the previous pixel's.
    """
    primaries = [entry(fam, setup, rgb) for rgb in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    taps = fam["taps"]
    return [primaries[channel][(burst * fam["alignments"] + alignment) * taps:][:taps]
            for burst in range(fam["bursts"]) for alignment in range(fam["alignments"]) for channel in range(3)]


# Where a pixel's taps fall among the output samples, as the blitters have
# it: pixel j is at alignment (j - 1) % alignments of chunk (j - 1) //
# alignments, a chunk is PERIOD output samples, and its tap 0 is on sample
# PERIOD * chunk + 2 * alignment + ORIGIN.
def period(fam: dict) -> int:
    return 7 if fam["alignments"] == 3 else 4


def origin(fam: dict) -> int:
    return 0 if fam["alignments"] == 3 else -4


def delay(fam: dict) -> float:
    """Output sample under the left edge of pixel 0, by the middle of its luma.

    The filters delay the picture by a few samples; the shader takes that
    out, so the picture stays where it is without the filter.
    """
    rows = table(fam, fam["presets"][0][2])
    scale = period(fam) / fam["alignments"]
    middles = []
    for alignment in range(fam["alignments"]):
        luma = [sum(RGB_TO_YIQ[0][c] * sum(rows[alignment * 3 + channel][tap][c] for channel in range(3))
                    for c in range(3)) for tap in range(fam["taps"])]
        middle = sum(tap * v for tap, v in enumerate(luma)) / sum(luma)
        middles.append(origin(fam) + 2 * alignment + middle - (1 + alignment) * scale)
    return sum(middles) / len(middles) - 0.5 * scale


def reach(fam: dict) -> int:
    """Pixels the shader has to look at for one point of the screen."""
    return math.ceil((fam["taps"] + 1 + 2 / 3) * fam["alignments"] / period(fam)) + 2


LICENSE = """   %(library)s, Copyright (C) 2006-2007 Shay Green, GNU Lesser General Public
   License, version 2.1 or later. Written by
   shared/shaders/tools/blargg_ntsc.py; change that, not this."""

KERNEL = """#version 450

/*
   Blargg's NTSC filter: the kernels of %(emulator)s's "%(preset)s".

%(license)s

   One row per burst phase (%(bursts)d), place of the pixel against the colour
   carrier (%(alignments)d) and input channel (red, green, blue): what a pixel with
   that channel at 1 adds to the %(taps)d output samples it spreads over. A column
   of zeroes either side lets blargg-ntsc.inc read between samples.
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
%(table)s
);

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

FAMILY = """#version 450

/*
   Blargg's NTSC filter as %(emulator)s has it (%(title)s): the picture pass.

%(license)s

   %(pixels)d pixels of a line become %(period)d output samples, each pixel spread over
   %(taps)d of them. %(phases)s
*/

#define NTSC_ALIGNMENTS %(alignments)d.0
#define NTSC_PERIOD %(period)d.0
#define NTSC_TAPS %(taps)d.0
#define NTSC_ORIGIN %(origin)d.0
#define NTSC_DELAY %(delay).4f
#define NTSC_REACH %(reach)d
#define NTSC_BURSTS %(bursts)d
#define NTSC_FRAME_PHASES %(frame_phases)du
#define NTSC_GAMMA %(gamma).4f

#pragma parameter NTSC_SCALE "Internal resolution scale (0 = auto)" 0.0 0.0 8.0 1.0
%(crawl)s
#include "blargg-ntsc.inc"
"""

PRESET = """# Blargg's NTSC filter: %(emulator)s's "%(preset)s" (%(library)s, Shay Green,
# LGPL 2.1 or later). Written by shared/shaders/tools/blargg_ntsc.py.

shaders = 2

# The kernels, as a texture: %(taps)d taps and a zero either side, by
# %(bursts)d burst phase(s) x %(alignments)d pixel places x 3 input channels. The filter
# of this pass is the one the next reads the game with ("Original"): linear,
# which averages the pixels of a higher internal resolution.
shader0 = %(name)s-kernel.slang
filter_linear0 = true
scale_type0 = absolute
scale_x0 = %(width)d
scale_y0 = %(rows)d

# The picture: every pixel of the game through its kernel.
shader1 = %(family)s.slang
filter_linear1 = true
scale_type1 = viewport
"""

PHASES = {
    3: "The burst phase moves on with every line and every frame.",
    2: "The burst phase moves on with every line, and between two values from frame to frame.",
    1: "Every line and frame has the same burst phase.",
}


def write() -> list[Path]:
    out = SHADERS / "blargg-ntsc"
    out.mkdir(exist_ok=True)
    written = []
    builtin = ["// Written by blargg_ntsc.py: the presets of shared/shaders/blargg-ntsc."]
    for family, fam in FAMILIES.items():
        info = dict(fam, family=family, period=period(fam), origin=origin(fam), delay=delay(fam), reach=reach(fam),
                    pixels=fam["alignments"], license=LICENSE % fam, phases=PHASES[fam["frame_phases"]],
                    rows=fam["bursts"] * fam["alignments"] * 3, width=fam["taps"] + 2,
                    crawl='#pragma parameter NTSC_CRAWL "Dot crawl" 1.0 0.0 1.0 1.0\n' if fam["bursts"] > 1 else "")
        path = out / f"{family}.slang"
        path.write_text(FAMILY % info)
        written.append(path)
        for key, label, preset in fam["presets"]:
            lines = []
            for index, row in enumerate(table(fam, preset)):
                burst, rest = divmod(index, fam["alignments"] * 3)
                lines.append(f"    // burst {burst}, pixel {rest // 3}, {'red green blue'.split()[rest % 3]}")
                lines += ["    vec3(" + ", ".join(f"{v:.6f}" for v in tap) + ")," for tap in row]
            lines[-1] = lines[-1].rstrip(",")
            one = dict(info, name=f"{family}-{key}", preset=label, table="\n".join(lines))
            for suffix, text in (("-kernel.slang", KERNEL), (".slangp", PRESET)):
                path = out / (one["name"] + suffix)
                path.write_text(text % one)
                written.append(path)
            builtin.append(f'{{"blargg-ntsc/{family}-{key}.slangp", "Blargg NTSC {fam["title"]} {label}"}},')
    path = Path(__file__).with_name("blargg_ntsc_builtin.inc")
    path.write_text("\n".join(builtin) + "\n")
    written.append(path)
    return written


if __name__ == "__main__":
    for path in write():
        print("wrote", path.relative_to(SHADERS.parents[1]))
