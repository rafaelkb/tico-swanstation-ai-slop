/*
   Blargg's NTSC filters, the TV filter of Snes9x, FCEUmm and Genesis Plus
   GX, as a shader: the pass that draws the picture. snes.slang, nes.slang,
   md.slang and sms.slang include it with the constants of their library.

   snes_ntsc, nes_ntsc, md_ntsc and sms_ntsc, Copyright (C) 2006-2007 Shay
   Green, GNU Lesser General Public License, version 2.1 or later.

   The filters turn NTSC_ALIGNMENTS pixels of a line into NTSC_PERIOD output
   samples: each pixel spreads over NTSC_TAPS of them, by a kernel that
   depends on where the pixel sits against the colour carrier and on the
   line's burst phase. The kernels come from the first pass of the preset
   (*-kernel.slang, one per setting of the filter); this pass adds up the
   pixels that reach a point of the screen.

   The filters take a line of 256 to 384 pixels, whichever console it is
   from. Two pixels of a 512 or 640 pixel line are one here, and so is every
   block of pixels of a higher internal resolution, so that the picture
   looks the same at any resolution scale.
*/

layout(push_constant) uniform Push
{
    vec4 SourceSize;
    vec4 OriginalSize;
    uint FrameCount;
    float NTSC_SCALE;
#if NTSC_BURSTS > 1
    float NTSC_CRAWL;
#endif
} params;

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

#include "../frame-scale.inc"

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

void main()
{
    // The frame's row under this point, and the line it belongs to.
    float row = min(floor(vTexCoord.y * params.OriginalSize.y), params.OriginalSize.y - 1.0);
    float v = (row + 0.5) * params.OriginalSize.w;

    // The burst phase moves on with every line and, as in the emulator the
    // filter is from, with every frame.
    float burst = 0.0;
#if NTSC_BURSTS > 1
    burst = floor((row + 0.5) / vScale.y);
    if (params.NTSC_CRAWL > 0.5)
        burst += float(params.FrameCount % NTSC_FRAME_PHASES);
    burst -= float(NTSC_BURSTS) * floor((burst + 0.5) / float(NTSC_BURSTS));
#endif

    // Where this point is among the output samples. The filter delays the
    // picture by a few samples, which NTSC_DELAY takes out.
    float width = params.OriginalSize.x / vScale.x;
    float pos = vTexCoord.x * width * (NTSC_PERIOD / NTSC_ALIGNMENTS) + NTSC_DELAY;

    // Pixel j is at place (j - 1) % NTSC_ALIGNMENTS of its chunk, and its
    // tap 0 is on output sample NTSC_PERIOD * chunk + 2 * place +
    // NTSC_ORIGIN. The first pixel whose taps can reach this point:
    float first = floor((pos - NTSC_TAPS - NTSC_ORIGIN) * NTSC_ALIGNMENTS / NTSC_PERIOD) + 1.0;

    vec3 color = vec3(0.0);
    for (int i = 0; i < NTSC_REACH; i++)
    {
        float pixel = first + float(i);
        float chunk = floor((pixel - 0.5) / NTSC_ALIGNMENTS);
        float place = pixel - 1.0 - NTSC_ALIGNMENTS * chunk;
        float tap = pos - (NTSC_PERIOD * chunk + 2.0 * place + NTSC_ORIGIN);
        // black outside the picture, as the filters have it
        if (tap <= -1.0 || tap >= NTSC_TAPS || pixel < 0.0 || pixel >= width)
            continue;

        // Linear filtering between the frame's pixels makes two taps the
        // average of a block of them, and one tap the pixel itself.
        float x = pixel * vScale.x;
        vec3 rgb;
        if (vScale.x > 1.5)
            rgb = 0.5 * (texture(Original, vec2((x + 0.25 * vScale.x) * params.OriginalSize.z, v)).rgb +
                         texture(Original, vec2((x + 0.75 * vScale.x) * params.OriginalSize.z, v)).rgb);
        else
            rgb = texture(Original, vec2((x + 0.5 * vScale.x) * params.OriginalSize.z, v)).rgb;
        // the gamma the filter gives the console's colours
        rgb = pow(rgb, vec3(NTSC_GAMMA));

        // The kernel row of this pixel's place and the line's burst phase,
        // read between the two output samples either side of this point.
        vec2 k = vec2(tap + 1.5, (burst * NTSC_ALIGNMENTS + place) * 3.0 + 0.5) * params.SourceSize.zw;
        color += texture(Source, k).rgb * rgb.r;
        k.y += params.SourceSize.w;
        color += texture(Source, k).rgb * rgb.g;
        k.y += params.SourceSize.w;
        color += texture(Source, k).rgb * rgb.b;
    }
    FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
