#version 450

/*
   Blargg's NTSC filter as Genesis Plus GX has it (Mega Drive): the picture pass.

   md_ntsc 0.1.2, Copyright (C) 2006-2007 Shay Green, GNU Lesser General Public
   License, version 2.1 or later. Written by
   shared/shaders/tools/blargg_ntsc.py; change that, not this.

   2 pixels of a line become 4 output samples, each pixel spread over
   16 of them. Every line and frame has the same burst phase.
*/

#define NTSC_ALIGNMENTS 2.0
#define NTSC_PERIOD 4.0
#define NTSC_TAPS 16.0
#define NTSC_ORIGIN -4.0
#define NTSC_DELAY -0.5019
#define NTSC_REACH 11
#define NTSC_BURSTS 1
#define NTSC_FRAME_PHASES 1u
#define NTSC_GAMMA 1.1333

#pragma parameter NTSC_SCALE "Internal resolution scale (0 = auto)" 0.0 0.0 8.0 1.0

#include "blargg-ntsc.inc"
