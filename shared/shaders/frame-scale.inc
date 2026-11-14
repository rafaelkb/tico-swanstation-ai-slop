// The pixels of the game in a frame, for shaders that work on the console's
// own lines and pixels whatever the internal resolution: include this in the
// vertex stage, where "params" has OriginalSize and NTSC_SCALE.
//
// A frame does not say which resolution the game runs at, so that is taken
// from its size: the lines are the whole division of the height nearest 240
// (an interlaced frame is two fields), and a line has 200 to 448 pixels.
// Returns the frame pixels in one pixel of a line (x) and in one line (y).
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
    if (width > 448.0)
        pixels *= 2.0;
    else if (width < 200.0)
        pixels = max(1.0, floor(pixels * 0.5));
    return vec2(pixels, lines);
}
