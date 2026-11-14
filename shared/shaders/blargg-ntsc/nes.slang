#version 450

/*
   Blargg's NTSC filter as FCEUmm has it (NES): the picture pass.

   nes_ntsc 0.2.2, Copyright (C) 2006-2007 Shay Green, GNU Lesser General Public
   License, version 2.1 or later. Written by
   shared/shaders/tools/blargg_ntsc.py; change that, not this.

   3 pixels of a line become 7 output samples, each pixel spread over
   14 of them. The burst phase moves on with every line, and between two values from frame to frame.
*/

#define NTSC_ALIGNMENTS 3.0
#define NTSC_PERIOD 7.0
#define NTSC_TAPS 14.0
#define NTSC_ORIGIN 0.0
#define NTSC_DELAY 2.6664
#define NTSC_REACH 9
#define NTSC_BURSTS 3
#define NTSC_FRAME_PHASES 2u
#define NTSC_GAMMA 1.0000

#pragma parameter NTSC_SCALE "Internal resolution scale (0 = auto)" 0.0 0.0 8.0 1.0
#pragma parameter NTSC_CRAWL "Dot crawl" 1.0 0.0 1.0 1.0

#include "blargg-ntsc.inc"
