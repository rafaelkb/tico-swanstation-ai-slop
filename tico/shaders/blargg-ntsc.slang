#version 450

/*
   Blargg's NTSC filter, the one Snes9x has, as a shader.

   snes_ntsc 0.2.2, Copyright (C) 2006-2007 Shay Green, GNU Lesser General
   Public License, version 2.1 or later. It turns every three pixels of a
   line into seven output samples: each pixel spreads over 14 of them, by a
   kernel that depends on where the pixel sits against the colour carrier
   (one of three places) and on the line's burst phase (one of three, moving
   on with every line and every frame). The kernels come from the first pass
   (blargg-ntsc-*-kernel.slang, one per preset of the filter); this pass
   adds up the seven pixels that reach a point of the screen.

   The PlayStation has its 256 pixel mode in common with the SNES, and its
   other modes are the same line at other pixel clocks. The 320, 368 and 384
   pixel modes are filtered a pixel at a time, like Snes9x does. Two pixels
   of the 512 and 640 pixel modes are one here, and so is every block of
   pixels of a higher internal resolution, so that the picture looks the
   same at any resolution scale.
*/

layout(push_constant) uniform Push
{
    vec4 SourceSize;
    vec4 OriginalSize;
    uint FrameCount;
    float NTSC_SCALE;
    float NTSC_CRAWL;
} params;

#pragma parameter NTSC_SCALE "Internal resolution scale (0 = auto)" 0.0 0.0 8.0 1.0
#pragma parameter NTSC_CRAWL "Dot crawl" 1.0 0.0 1.0 1.0

layout(std140, set = 0, binding = 0) uniform UBO
{
    mat4 MVP;
} global;

#pragma stage vertex
layout(location = 0) in vec4 Position;
layout(location = 1) in vec2 TexCoord;
layout(location = 0) out vec2 vTexCoord;
// frame pixels in one pixel of the line (x) and in one line (y)
layout(location = 1) flat out vec2 vScale;

// The frame does not say which resolution the game runs at, so that is taken
// from its size: the lines are the whole division of the height nearest 240
// (an interlaced frame is two fields), and a line has 256 to 384 pixels.
vec2 FrameScale(vec2 size)
{
    if (params.NTSC_SCALE > 0.5)
        return vec2(params.NTSC_SCALE);

    float lines = 1.0;
    float miss = 1.0e9;
    for (float n = 1.0; n < 16.5; n += 1.0)
    {
        float count = size.y / n;
        if (abs(count - floor(count + 0.5)) > 0.01)
            continue;
        // PAL's 256 and 288 lines are nearer than a line count below 240
        float d = count > 240.0 ? (count - 240.0) * 0.5 : 240.0 - count;
        if (d < miss - 0.01)
        {
            miss = d;
            lines = n;
        }
    }
    if (miss > 64.0)
        lines = max(1.0, floor(size.y / 240.0 + 0.5));

    float pixels = lines;
    float width = size.x / pixels;
    if (width > 400.0)
        pixels *= 2.0;
    else if (width < 200.0)
        pixels = max(1.0, floor(pixels * 0.5));
    return vec2(pixels, lines);
}

void main()
{
    gl_Position = global.MVP * Position;
    vTexCoord = TexCoord;
    vScale = FrameScale(params.OriginalSize.xy);
}

#pragma stage fragment
layout(location = 0) in vec2 vTexCoord;
layout(location = 1) flat in vec2 vScale;
layout(location = 0) out vec4 FragColor;
layout(set = 0, binding = 2) uniform sampler2D Source;   // the kernels
layout(set = 0, binding = 3) uniform sampler2D Original; // the game

// snes_ntsc's gamma, "to match common PC's 2.2 gamma to TV's 2.65 gamma"
const float kGamma = 1.1333;

void main()
{
    // The frame's row under this point, and the line it belongs to. The
    // burst phase moves on with every line and, as in Snes9x, every frame.
    float row = min(floor(vTexCoord.y * params.OriginalSize.y), params.OriginalSize.y - 1.0);
    float v = (row + 0.5) * params.OriginalSize.w;
    float burst = floor((row + 0.5) / vScale.y);
    if (params.NTSC_CRAWL > 0.5)
        burst += float(params.FrameCount % 3u);
    burst -= 3.0 * floor((burst + 0.5) / 3.0);

    // Where this point is among the output samples: 7 to every 3 pixels,
    // pixel 0's kernel being centred on sample 23/6.
    float width = params.OriginalSize.x / vScale.x;
    float pos = vTexCoord.x * width * (7.0 / 3.0) + 8.0 / 3.0;

    // snes_ntsc takes pixels in chunks of three, pixel 3c + 1 first, and the
    // kernels of a chunk's pixels start at its output samples 0, 2 and 4.
    // The first of the seven pixels whose 14 samples reach this point:
    float chunk = floor((pos - 14.0) / 7.0);
    float into = pos - 14.0 - 7.0 * chunk;
    float first = 3.0 * chunk + (into < 2.0 ? 2.0 : into < 4.0 ? 3.0 : 4.0);

    vec3 color = vec3(0.0);
    for (int i = 0; i < 7; i++)
    {
        float pixel = first + float(i);
        if (pixel < 0.0 || pixel >= width)
            continue; // black outside the picture, as snes_ntsc has it

        // Linear filtering between the frame's pixels makes two taps the
        // average of a block of them, and one tap the pixel itself.
        float x = pixel * vScale.x;
        vec3 rgb;
        if (vScale.x > 1.5)
            rgb = 0.5 * (texture(Original, vec2((x + 0.25 * vScale.x) * params.OriginalSize.z, v)).rgb +
                         texture(Original, vec2((x + 0.75 * vScale.x) * params.OriginalSize.z, v)).rgb);
        else
            rgb = texture(Original, vec2((x + 0.5 * vScale.x) * params.OriginalSize.z, v)).rgb;
        rgb = pow(rgb, vec3(kGamma));

        // The kernel row of this pixel's place and the line's burst phase,
        // read between the two output samples either side of this point.
        chunk = floor((pixel - 0.5) / 3.0);
        float place = pixel - 1.0 - 3.0 * chunk;
        float tap = pos - (7.0 * chunk + 2.0 * place);
        vec2 k = vec2(tap + 1.5, (burst * 3.0 + place) * 3.0 + 0.5) * params.SourceSize.zw;
        color += texture(Source, k).rgb * rgb.r;
        k.y += params.SourceSize.w;
        color += texture(Source, k).rgb * rgb.g;
        k.y += params.SourceSize.w;
        color += texture(Source, k).rgb * rgb.b;
    }
    FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
