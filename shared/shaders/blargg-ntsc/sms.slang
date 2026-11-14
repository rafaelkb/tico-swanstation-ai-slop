#version 450

/*
   Blargg's NTSC filter as Genesis Plus GX has it (Master System): the picture pass.

   sms_ntsc 0.2.3, Copyright (C) 2006-2007 Shay Green, GNU Lesser General Public
   License, version 2.1 or later. Written by
   shared/shaders/tools/blargg_ntsc.py; change that, not this.

   3 pixels of a line become 7 output samples, each pixel spread over
   14 of them. Every line and frame has the same burst phase.
*/

#define NTSC_ALIGNMENTS 3.0
#define NTSC_PERIOD 7.0
#define NTSC_TAPS 14.0
#define NTSC_ORIGIN 0.0
#define NTSC_DELAY 2.6587
#define NTSC_REACH 9
#define NTSC_BURSTS 1
#define NTSC_FRAME_PHASES 1u
#define NTSC_GAMMA 1.1333

#pragma parameter NTSC_SCALE "Internal resolution scale (0 = auto)" 0.0 0.0 8.0 1.0

#include "blargg-ntsc.inc"
