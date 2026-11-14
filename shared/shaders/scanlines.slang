#version 450

/*
   Scanlines, the "Scanline" video filter of YabaSanshiro (yglshaderes.c,
   YglBlitScanlineFilter; GPL 2 or later): the screen in bands a whole number
   of pixels high, two to each line of the game, every other one black.
*/

layout(push_constant) uniform Push
{
    vec4 OriginalSize;
    vec4 OutputSize;
    float NTSC_SCALE;
    float SCANLINE_DARK;
} params;

#pragma parameter NTSC_SCALE "Internal resolution scale (0 = auto)" 0.0 0.0 8.0 1.0
#pragma parameter SCANLINE_DARK "Darkness of the lines" 1.0 0.0 1.0 0.05

layout(std140, set = 0, binding = 0) uniform UBO
{
    mat4 MVP;
} global;

#pragma stage vertex
layout(location = 0) in vec4 Position;
layout(location = 1) in vec2 TexCoord;
layout(location = 0) out vec2 vTexCoord;
// screen pixels in one band
layout(location = 1) flat out float vBand;

#include "frame-scale.inc"

void main()
{
    gl_Position = global.MVP * Position;
    vTexCoord = TexCoord;
    float lines = params.OriginalSize.y / FrameScale(params.OriginalSize.xy).y;
    vBand = max(1.0, floor(params.OutputSize.y / (lines * 2.0)));
}

#pragma stage fragment
layout(location = 0) in vec2 vTexCoord;
layout(location = 1) flat in float vBand;
layout(location = 0) out vec4 FragColor;
layout(set = 0, binding = 2) uniform sampler2D Source;

void main()
{
    vec3 color = texture(Source, vTexCoord).rgb;
    float band = floor(vTexCoord.y * params.OutputSize.y / vBand);
    if (band - 2.0 * floor(band * 0.5) > 0.5)
        color *= 1.0 - params.SCANLINE_DARK;
    FragColor = vec4(color, 1.0);
}
