import type { AuroraBundle, AuroraFrame } from "../src/aurora-time";

/**
 * One byte-exact NOAA SWPC OVATION 2020 global grid, kept so the equatorial
 * seam regression runs against real operational values rather than a hand
 * drawn field.
 *
 * Source          https://services.swpc.noaa.gov/json/ovation_aurora_latest.json
 * Snapshot        /mnt/d/space-explorer/environment-history/aurora/ovation-20260807131700.json
 * Observed        2026-08-07T11:42:00Z
 * Forecast valid  2026-08-07T13:17:00Z (95 minute lead)
 * Grid            360 x 181 one-degree cells, 0-359E, 90S-90N, every cell valid
 *
 * The 65,160 probability bytes below are NOAA's bytes, run-length encoded as
 * `value` or `valuexcount` only to keep the fixture small and readable.
 * Nothing is rounded, resampled, or reordered.
 */
export const REAL_OVATION_FRAME = {
  observedAt: "2026-08-07T11:42:00Z",
  validAt: "2026-08-07T13:17:00Z",
  leadMinutes: 95,
  longitudeCount: 360,
  latitudeCount: 181,
  latitudeStartDeg: -90,
  latitudeStepDeg: 1,
} as const;

const RUN_LENGTH_PROBABILITY = [
  "6x85,5x88,4,3,2x2,1x2,0x11,1x5,2x16,3,4x2,5,6x145,0x360,7x9,8x57,7x29,6x57,7x19,6x2,5x2,4,3,2x2,1x2,0x4,",
  "1x4,2x4,3x4,4x14,5,6x2,7,8x67,7x78,8x14,9x51,8x18,7x22,6x39,7x29,6x2,5,4x2,3,2,1x5,2x3,3x3,4x3,5x5,6x12,",
  "7x2,8,9x57,8x102,9x24,10x12,9x18,8x13,7x13,6x29,5x5,6x28,7x19,6x2,5x2,4,3,2x5,3x2,4x2,5x3,6x3,7x11,8x6,9",
  "x3,10x36,9x21,8x29,7x17,8x3,7x28,8x11,7x7,8x15,9x21,10x3,9x18,8x9,7x9,6x11,5x27,4x9,5x25,6x15,7x3,6x5,5x",
  "2,4,3x4,4x2,5x2,6x4,7x3,8x11,9x8,10x34,9x16,8x16,7x22,6x15,7x5,6x20,7x18,6x7,7x13,8x12,9x27,8x8,7x8,6x7,",
  "5x10,4x16,3x28,4x20,5x12,6x9,5x2,4x5,5x2,6x4,7x4,8x8,9x11,10x27,9x14,8x12,7x14,6x20,5x50,6x10,5x10,6x11,",
  "7x9,8x12,9x11,8x10,7x6,6x7,5x6,4x9,3x14,2x33,3x18,4x12,5x12,4x2,5x3,6x4,7x6,8x9,9x12,10x16,9x14,8x10,7x1",
  "1,6x12,5x20,4x55,5x6,4x11,5x10,6x9,7x9,8x20,7x7,6x5,5x6,4x6,3x8,2x18,1x20,2x25,3x12,4x10,5x2,4x3,5x5,6x6",
  ",7x7,8x8,9x33,8x9,7x8,6x10,5x11,4x21,3x57,4x4,3x12,4x10,5x8,6x8,7x25,6x6,5x5,4x5,3x6,2x10,1x53,2x15,3x10",
  ",4x10,5x6,6x6,7x7,8x9,9x23,8x9,7x7,6x8,5x9,4x11,3x22,2x55,3x5,2x10,3x12,4x8,5x7,6x8,7x15,6x7,5x5,4x4,3x6",
  ",2x8,1x20,0x13,1x34,2x12,3x9,4x8,5x6,6x6,7x7,8x9,9x14,8x10,7x7,6x6,5x8,4x9,3x13,2x23,1x11,2x7,1x23,2x15,",
  "1x5,2x15,3x9,4x8,5x7,6x21,5x5,4x5,3x5,2x7,1x13,0x42,1x21,2x11,3x8,4x6,5x6,6x6,7x7,8x26,7x7,6x6,5x7,4x7,3",
  "x11,2x18,1x86,2x13,3x8,4x7,5x7,6x14,5x6,4x5,3x4,2x6,1x12,0x53,1x17,2x10,3x7,4x6,5x6,6x5,7x7,8x21,7x7,6x6",
  ",5x6,4x6,3x9,2x14,1x106,2x11,3x7,4x7,5x9,6x5,5x8,4x5,3x4,2x6,1x10,0x60,1x15,2x9,3x7,4x5,5x6,6x5,7x6,8x18",
  ",7x7,6x5,5x5,4x7,3x7,2x12,1x36,0x48,1x7,0x8,1x21,2x10,3x7,4x6,5x19,4x4,3x5,2x5,1x9,0x64,1x14,2x9,3x5,4x6",
  ",5x5,6x5,7x6,8x15,7x7,6x5,5x5,4x5,3x7,2x10,1x27,0x87,1x18,2x9,3x7,4x6,5x16,4x5,3x4,2x5,1x9,0x65,1x13,2x8",
  ",3x5,4x5,5x5,6x5,7x6,8x14,7x6,6x5,5x5,4x5,3x6,2x9,1x24,0x102,1x16,2x8,3x6,4x5,5x16,4x4,3x4,2x5,1x8,0x66,",
  "1x12,2x7,3x5,4x5,5x5,6x5,7x6,8x13,7x6,6x4,5x5,4x5,3x5,2x9,1x19,0x115,1x15,2x8,3x5,4x5,5x17,4x3,3x4,2x4,1",
  "x8,0x65,1x11,2x6,3x5,4x5,5x5,6x5,7x5,8x14,7x6,6x4,5x4,4x5,3x5,2x8,1x16,0x126,1x14,2x7,3x5,4x4,5x6,6x8,5x",
  "4,4x3,3x4,2x4,1x8,0x62,1x11,2x5,3x5,4x4,5x5,6x5,7x5,8x15,7x6,6x4,5x4,4x4,3x5,2x7,1x14,0x135,1x13,2x7,3x5",
  ",4x4,5x4,6x11,5x4,4x3,3x3,2x3,1x9,0x58,1x10,2x6,3x4,4x4,5x5,6x4,7x6,8x17,7x5,6x4,5x3,4x5,3x4,2x7,1x12,0x",
  "142,1x13,2x7,3x4,4x4,5x3,6x5,7x5,6x4,5x3,4x3,3x3,2x3,1x9,0x52,1x12,2x5,3x4,4x4,5x3,6x5,7x5,8x8,9x6,8x7,7",
  "x4,6x3,5x4,4x4,3x5,2x6,1x11,0x148,1x13,2x6,3x4,4x4,5x3,6x3,7x10,6x3,5x2,4x3,3x3,2x3,1x11,0x43,1x13,2x5,3",
  "x4,4x4,5x4,6x3,7x5,8x6,9x13,8x5,7x4,6x3,5x4,4x3,3x5,2x5,1x10,0x154,1x14,2x6,3x4,4x3,5x3,6x3,7x4,8x4,7x4,",
  "6x2,5x3,4x2,3x3,2x4,1x15,0x29,1x16,2x6,3x4,4x3,5x3,6x3,7x4,8x5,9x19,8x4,7x4,6x3,5x3,4x4,3x4,2x5,1x10,0x1",
  "58,1x14,2x6,3x4,4x3,5x3,6x2,7x4,8x8,7x3,6x2,5x2,4x2,3x3,2x5,1x23,0x13,1x17,2x6,3x3,4x4,5x3,6x3,7x3,8x4,9",
  "x4,10x16,9x4,8x4,7x3,6x3,5x3,4x3,3x4,2x5,1x9,0x163,1x14,2x7,3x3,4x3,5x3,6x2,7x3,8x10,7x3,6x2,5x2,4x3,3x3",
  ",2x5,1x44,2x7,3x4,4x3,5x3,6x3,7x3,8x2,9x4,10x5,11x13,10x4,9x4,8x3,7x3,6x2,5x3,4x4,3x3,2x5,1x8,0x168,1x14",
  ",2x7,3x4,4x3,5x2,6x3,7x2,8x4,9x4,8x4,7x2,6x2,5x3,4x3,3x3,2x6,1x33,2x8,3x5,4x4,5x2,6x3,7x3,8x2,9x3,10x3,1",
  "1x5,12x12,11x4,10x3,9x3,8x3,7x2,6x3,5x3,4x3,3x4,2x4,1x8,0x172,1x15,2x6,3x4,4x3,5x3,6x2,7x3,8x3,9x6,8x3,7",
  "x3,6x2,5x2,4x4,3x4,2x7,1x21,2x9,3x5,4x4,5x3,6x3,7x2,8x3,9x2,10x3,11x3,12x3,13x13,12x4,11x3,10x3,9x2,8x3,",
  "7x2,6x3,5x3,4x3,3x3,2x5,1x7,0x177,1x14,2x7,3x4,4x3,5x2,6x3,7x2,8x3,9x7,8x3,7x3,6x3,5x2,4x4,3x5,2x25,3x6,",
  "4x5,5x3,6x3,7x3,8x2,9x3,10x2,11x2,12x3,13x3,14x15,13x3,12x3,11x2,10x2,9x3,8x2,7x2,6x3,5x2,4x3,3x3,2x5,1x",
  "7,0x182,1x14,2x6,3x4,4x3,5x3,6x2,7x3,8x2,9x9,8x3,7x3,6x3,5x3,4x4,3x24,4x5,5x4,6x4,7x3,8x2,9x3,10x2,11x2,",
  "12x2,13x3,14x3,15x4,16x8,15x4,14x3,13x2,12x2,11x2,10x2,9x3,8x2,7x2,6x2,5x3,4x3,3x3,2x4,1x7,0x187,1x14,2x",
  "6,3x4,4x3,5x3,6x2,7x2,8x3,9x9,8x4,7x3,6x3,5x5,4x20,5x4,6x4,7x3,8x3,9x3,10x2,11x3,12x2,13x2,14x3,15x2,16x",
  "4,17x11,16x3,15x2,14x3,13x2,12x2,11,10x2,9x2,8x2,7x3,6x2,5x2,4x3,3x4,2x4,1x6,0x193,1x13,2x6,3x4,4x3,5x2,",
  "6x3,7x2,8x3,9x10,8x4,7x4,6x6,5x13,6x5,7x4,8x3,9x2,10x3,11x2,12x3,13x2,14x2,15x3,16x3,17x3,18x14,17x2,16x",
  "3,15x2,14,13x2,12x2,11,10x2,9x2,8x2,7x2,6x2,5x3,4x3,3x3,2x4,1x6,0x199,1x12,2x6,3x4,4x3,5x2,6x3,7x2,8x4,9",
  "x11,8x6,7x17,8x4,9x3,10x3,11x2,12x3,13x2,14x2,15x2,16x3,17x2,18x3,19x5,20x7,19x4,18x3,17x2,16x2,15x2,14x",
  "2,13,12,11x2,10x2,9x2,8,7x3,6x2,5x2,4x3,3x3,2x5,1x6,0x204,1x11,2x6,3x4,4x3,5x2,6x3,7x3,8x3,9x31,10x4,11x",
  "3,12x2,13x3,14x2,15x2,16x2,17x2,18x3,19x2,20x4,21x10,20x4,19x2,18x2,17x2,16x2,15,14x2,13x2,12,11,10x2,9x",
  "2,8x2,7x2,6x2,5x3,4x2,3x4,2x4,1x6,0x209,1x11,2x6,3x4,4x3,5x3,6x2,7x3,8x4,9x5,10x17,11x6,12x3,13x3,14x2,1",
  "5x3,16x2,17x2,18x2,19x2,20x3,21x3,22x10,21x4,20x2,19x2,18x2,17x2,16,15x2,14,13x2,12,11x2,10,9x2,8x2,7x2,",
  "6x2,5x3,4x3,3x3,2x4,1x6,0x215,1x10,2x6,3x4,4x3,5x3,6x3,7x3,8x3,9x4,10x5,11x7,12x6,13x4,14x4,15x2,16x2,17",
  "x3,18x2,19x2,20x2,21x3,22x5,23x4,22x4,21x3,20x2,19x2,18x2,17x2,16,15x2,14,13x2,12,11x2,10x2,9,8x2,7x2,6x",
  "2,5x3,4x2,3x4,2x4,1x6,0x220,1x10,2x6,3x5,4x3,5x3,6x3,7x3,8x3,9x3,10x3,11x4,12x5,13x4,14x4,15x3,16x2,17x3",
  ",18x2,19x3,20x2,21x3,22x12,21x3,20x2,19x2,18x2,17,16x2,15,14x2,13,12x2,11x2,10,9x2,8x2,7x2,6x2,5x2,4x3,3",
  "x3,2x5,1x6,0x225,1x11,2x6,3x4,4x4,5x3,6x3,7x3,8x2,9x3,10x3,11x3,12x3,13x4,14x3,15x4,16x2,17x3,18x3,19x2,",
  "20x4,21x12,20x2,19x2,18x2,17x2,16x2,15,14x2,13x2,12,11x2,10,9x2,8x2,7x2,6x3,5,4x4,3x3,2x4,1x6,0x232,1x10",
  ",2x7,3x5,4x3,5x3,6x3,7x3,8x3,9x2,10x3,11x3,12x3,13x3,14x3,15x3,16x3,17x3,18x4,19x5,20x3,19x5,18x3,17x2,1",
  "6x2,15x2,14,13x2,12x2,11,10x2,9x2,8x2,7x2,6x2,5x3,4x3,3x3,2x5,1x5,0x238,1x11,2x7,3x5,4x4,5x3,6x3,7x3,8x2",
  ",9x3,10x3,11x3,12x3,13x3,14x4,15x3,16x5,17x9,16x4,15x2,14x2,13x3,12,11x2,10x2,9x2,8x2,7x3,6x2,5x3,4x3,3x",
  "4,2x4,1x6,0x100,1x15,0x129,1x11,2x8,3x5,4x4,5x3,6x3,7x3,8x3,9x3,10x4,11x4,12x4,13x5,14x10,13x4,12x3,11x2",
  ",10x2,9x3,8x2,7x2,6x3,5x3,4x3,3x4,2x5,1x6,0x96,1x33,0x121,1x14,2x8,3x5,4x3,5x4,6x4,7x3,8x4,9x5,10x6,11x1",
  "0,10x5,9x3,8x3,7x3,6x3,5x3,4x4,3x4,2x5,1x7,0x95,1x44,0x119,1x15,2x8,3x5,4x4,5x5,6x5,7x7,8x14,7x5,6x4,5x3",
  ",4x4,3x5,2x6,1x8,0x92,1x56,0x118,1x17,2x7,3x7,4x7,5x24,4x6,3x5,2x6,1x10,0x91,1x65,0x122,1x16,2x9,3x14,4x",
  "7,3x11,2x8,1x11,0x93,1x71,0x128,1x17,2x30,1x13,0x100,1x72,0x137,1x42,0x112,1x66,0x159,1x5,0x140,1x48,0x1",
  "4799,1x123,0x6,1x42,0x44,1x145,2x172,1x3,0x37,1x2,2x146,4x95,3x57,4x18,3x3,2x2,1x2,0x19,1x16,2,3x2,4x145",
  ",0x15074,1x5,0x351,1x32,0x7,1x6,0x5,1x15,0x295,1x84,0x278,1x86,0x9,1x5,0x265,1x99,0x266,1x111,0x256,1x10",
  "6,0x262,1x57,0x34,1x3,0x170,1x25,0x82,1x12,0x234,1x41,0x314,1x9,2x25,1x18,0x303,1x8,2x8,3x13,2x18,1x15,0",
  "x293,1x7,2x6,3x9,4x7,3x20,2x8,1x16,0x281,1x8,2x5,3x5,4x10,5x6,4x19,3x7,2x7,1x17,0x269,1x9,2x6,3x4,4x5,5x",
  "9,6x9,5x17,4x7,3x6,2x6,1x17,0x258,1x10,2x6,3x4,4x5,5x4,6x8,7x11,6x16,5x7,4x6,3x6,2x6,1x15,0x248,1x11,2x6",
  ",3x5,4x4,5x4,6x5,7x8,8x10,7x15,6x10,5x6,4x5,3x6,2x6,1x14,0x233,1x15,2x7,3x5,4x5,5x4,6x4,7x4,8x8,9x9,8x12",
  ",7x12,6x10,5x5,4x5,3x5,2x7,1x12,0x217,1x20,2x9,3x5,4x5,5x4,6x3,7x4,8x5,9x8,10x8,9x9,8x8,7x17,6x9,5x5,4x4",
  ",3x5,2x6,1x12,0x188,1x34,2x11,3x7,4x5,5x4,6x4,7x4,8x4,9x4,10x8,11x7,10x8,9x6,8x7,7x24,6x7,5x5,4x4,3x5,2x",
  "5,1x12,0x132,1x70,2x16,3x7,4x8,5x5,6x4,7x4,8x4,9x3,10x5,11x7,12x8,11x7,10x5,9x5,8x5,7x33,6x6,5x4,4x4,3x4",
  ",2x6,1x11,0x110,1x46,2x41,3x13,4x8,5x6,6x6,7x4,8x4,9x4,10x4,11x4,12x8,13x7,12x7,11x4,10x4,9x4,8x4,7x6,6x",
  "15,7x21,6x5,5x3,4x4,3x4,2x6,1x12,0x92,1x39,2x26,3x30,4x12,5x8,6x7,7x4,8x6,9x4,10x5,11x4,12x5,13x9,14x3,1",
  "3x8,12x5,11x3,10x4,9x3,8x4,7x5,6x9,5x3,6x10,7x8,8x8,7x6,6x4,5x4,4x3,3x5,2x5,1x14,0x74,1x36,2x21,3x17,4x2",
  "3,5x14,6x8,7x7,8x6,9x5,10x6,11x4,12x5,13x6,14x19,13x5,12x4,11x3,10x3,9x3,8x3,7x4,6x5,5x18,6x6,7x7,8x12,7",
  "x5,6x4,5x3,4x4,3x4,2x6,1x17,0x50,1x40,2x20,3x14,4x13,5x14,6x14,7x11,8x8,9x6,10x6,11x6,12x6,13x5,14x7,15x",
  "17,14x5,13x4,12x3,11x4,10x2,9x4,8x3,7x3,6x4,5x7,4x13,5x6,6x6,7x5,8x15,7x4,6x4,5x3,4x4,3x5,2x6,1x23,0x17,",
  "1x50,2x21,3x13,4x11,5x10,6x10,7x11,8x11,9x9,10x7,11x7,12x6,13x6,14x7,15x9,16x12,15x8,14x4,13x4,12x3,11x3",
  ",10x3,9x3,8x3,7x3,6x4,5x5,4x10,3x2,4x11,5x5,6x5,7x5,8x16,7x4,6x4,5x4,4x4,3x5,2x7,1x72,2x21,3x15,4x10,5x9",
  ",6x9,7x8,8x9,9x9,10x8,11x8,12x7,13x7,14x7,15x7,16x27,15x6,14x4,13x3,12x3,11x3,10x3,9x3,8x3,7x4,6x3,5x5,4",
  "x5,3x20,4x6,5x5,6x5,7x5,8x16,7x4,6x4,5x4,4x4,3x6,2x9,1x47,2x28,3x15,4x12,5x9,6x8,7x8,8x8,9x7,10x8,11x7,1",
  "2x7,13x7,14x7,15x8,16x8,17x23,16x6,15x5,14x4,13x3,12x3,11x3,10x3,9x3,8x4,7x3,6x3,5x4,4x6,3x8,2x11,3x10,4",
  "x6,5x5,6x5,7x6,8x12,7x6,6x4,5x4,4x5,3x7,2x12,1x21,2x31,3x17,4x13,5x11,6x9,7x8,8x7,9x7,10x8,11x7,12x7,13x",
  "6,14x7,15x7,16x8,17x15,18x4,17x11,16x6,15x4,14x4,13x3,12x4,11x3,10x3,9x3,8x3,7x4,6x3,5x4,4x5,3x7,2x24,3x",
  "8,4x6,5x5,6x6,7x10,8,7x10,6x5,5x5,4x6,3x8,2x35,3x25,4x14,5x12,6x12,7x9,8x8,9x8,10x7,11x8,12x7,13x7,14x7,",
  "15x7,16x8,17x30,16x5,15x5,14x4,13x3,12x4,11x3,10x3,9x3,8x3,7x4,6x4,5x4,4x4,3x7,2x12,1x8,2x14,3x8,4x7,5x6",
  ",6x7,7x14,6x7,5x6,4x8,3x12,2x18,3x12,4x19,5x14,6x12,7x13,8x11,9x9,10x8,11x9,12x8,13x8,14x7,15x8,16x11,17",
  "x17,16x8,15x5,14x5,13x4,12x3,11x3,10x4,9x3,8x3,7x4,6x3,5x5,4x4,3x6,2x10,1x25,2x11,3x9,4x7,5x7,6x22,5x8,4",
  "x11,3x24,4x11,5x16,6x14,7x13,8x17,9x14,10x11,11x11,12x10,13x8,14x10,15x13,16x10,15x11,14x6,13x4,12x4,11x",
  "4,10x4,9x3,8x4,7x3,6x4,5x4,4x5,3x6,2x9,1x37,2x12,3x10,4x8,5x33,4x31,5x9,6x13,7x14,8x16,9x30,10x17,11x13,",
  "12x12,13x13,14x22,13x9,12x5,11x5,10x4,9x4,8x4,7x4,6x4,5x5,4x5,3x6,2x9,1x49,2x15,3x10,4x11,5x22,4x21,5x9,",
  "6x9,7x11,8x13,9x54,10x25,11x17,12x28,11x9,10x6,9x5,8x4,7x5,6x5,5x4,4x6,3x6,2x9,1x63,2x17,3x11,4x32,5x19,",
  "6x6,7x9,8x9,9x16,10x25,9x54,10x38,9x9,8x7,7x6,6x5,5x5,4x6,3x7,2x9,1x30,0x18,1x33,2x16,3x16,4x20,5x12,6x9",
  ",7x8,8x9,9x13,10x22,9x20,8x79,7x10,6x7,5x7,4x7,3x7,2x10,1x28,0x33,1x38,2x15,3x18,4x12,5x9,6x12,7x8,8x9,9",
  "x37,8x16,7x60,6x19,5x10,4x9,3x9,2x11,1x25,0x48,1x41,2x19,3x14,4x9,5x8,6,5x6,6x9,7x10,8x35,7x17,6x32,5x40",
  ",4x14,3x12,2x12,1x25,0x60,1x46,2x20,3x11,4x9,5x2,4x7,5x11,6x14,7x22,6x21,5x31,4x40,3x17,2x16,1x25,0x89,1",
  "x36,2x18,3x11,4x2,3x9,4x14,5x51,4x37,3x37,2x21,1x28,0x108,1x34,2x17,3x4,2x10,3x19,4x47,3x49,2x34,1x32,0x",
  "119,1x40,2x10,1x3,2x28,3x60,2x54,1x41,0x128,1x67,2x105,1x49,0x143,1x91,2x42,1x81,0x153,1x204,0x170,1x21,",
  "0x3,1x159,0x243,1x71,0x964",
].join("");

/** NOAA's exact probability bytes, latitude-major and south-to-north. */
export function realOvationProbabilityBytes(): Uint8Array {
  const expected = REAL_OVATION_FRAME.longitudeCount * REAL_OVATION_FRAME.latitudeCount;
  const bytes = new Uint8Array(expected);
  let cursor = 0;
  for (const run of RUN_LENGTH_PROBABILITY.split(",")) {
    const [value, count] = run.split("x");
    bytes.fill(Number(value), cursor, cursor + Number(count ?? 1));
    cursor += Number(count ?? 1);
  }
  if (cursor !== expected) throw new Error(`OVATION fixture expanded to ${cursor} cells; expected ${expected}`);
  return bytes;
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary);
}

/**
 * Wraps probability bytes in the published `noaa-ovation-history.v1` shape so
 * tests drive the same bundle the browser receives. `probability` defaults to
 * the real NOAA frame; callers pass their own bytes to exercise fields the
 * operational grid does not happen to contain.
 */
export function ovationBundle(probability: Uint8Array = realOvationProbabilityBytes()): AuroraBundle {
  const cells = REAL_OVATION_FRAME.longitudeCount * REAL_OVATION_FRAME.latitudeCount;
  if (probability.length !== cells) throw new Error(`OVATION test grid must contain ${cells} cells`);
  const validity = new Uint8Array(Math.ceil(cells / 8)).fill(0xff);
  let maximum = 0;
  let northMaximum = 0;
  let southMaximum = 0;
  for (let index = 0; index < cells; index += 1) {
    const value = probability[index]!;
    const latitude = REAL_OVATION_FRAME.latitudeStartDeg
      + Math.floor(index / REAL_OVATION_FRAME.longitudeCount) * REAL_OVATION_FRAME.latitudeStepDeg;
    if (value > maximum) maximum = value;
    if (latitude > 0 && value > northMaximum) northMaximum = value;
    if (latitude < 0 && value > southMaximum) southMaximum = value;
  }
  const frame: AuroraFrame = {
    observedAt: REAL_OVATION_FRAME.observedAt,
    validAt: REAL_OVATION_FRAME.validAt,
    leadMinutes: REAL_OVATION_FRAME.leadMinutes,
    probabilityU8: toBase64(probability),
    validityBits: toBase64(validity),
    validCellCount: cells,
    missingCellCount: 0,
    maximumProbabilityPercent: maximum,
    hemispheres: {
      north: { validCellCount: 32_400, maximumProbabilityPercent: northMaximum },
      south: { validCellCount: 32_400, maximumProbabilityPercent: southMaximum },
    },
  };
  return {
    schemaVersion: "noaa-ovation-history.v1",
    product: "NOAA SWPC OVATION 2020 Aurora Forecast",
    status: "model",
    temporalKind: "observation-driven forecast",
    retrievedAt: "2026-08-07T13:00:00Z",
    source: {
      currentNumericGrid: "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json",
      productPage: "https://www.spaceweather.gov/products/aurora-30-minute-forecast",
      wmoProductPage: "https://www.spaceweather.gov/content/wmo/auroral-activity",
      northImageHistoryManifest: "north",
      southImageHistoryManifest: "south",
      nceiProductInventory: "inventory",
      model: "OVATION 2020",
      inputs: "L1 solar wind and IMF",
      sourceCadenceMinutes: 5,
    },
    sourceAvailability: {
      publicNumericDistribution: "latest grid only",
      publicRenderedImageHistoryHours: 24,
      publicNumericHistoryHours: 0,
      historyMethod: "exact NOAA numeric grids accumulated by scheduled bigmem snapshots",
      notUsed: "rendered-image reconstruction",
      inventoryCheckedAt: "2026-08-07T13:00:00Z",
    },
    grid: {
      longitudeStartDeg: 0,
      longitudeStepDeg: 1,
      longitudeCount: REAL_OVATION_FRAME.longitudeCount,
      latitudeStartDeg: REAL_OVATION_FRAME.latitudeStartDeg,
      latitudeStepDeg: REAL_OVATION_FRAME.latitudeStepDeg,
      latitudeCount: REAL_OVATION_FRAME.latitudeCount,
      order: "latitude-major, south-to-north, west-to-east",
      longitudeConvention: "0 <= east longitude < 360",
      sourceCoordinateOrder: "longitude-major, south-to-north within each longitude",
    },
    encoding: {
      probability: "uint8-base64",
      validity: "bitset-lsb-first-base64",
      validRangePercent: [0, 100],
      missingRepresentation: "validity bit 0; paired probability byte must be ignored",
    },
    quantity: {
      name: "Aurora viewing probability",
      units: "%",
      definition: "OVATION model probability of visible aurora under dark, clear viewing conditions",
    },
    time: {
      requestedHistoryHours: 48,
      requestedFrom: "2026-08-05T13:00:00Z",
      requestedTo: "2026-08-07T13:17:00Z",
      availableFrom: REAL_OVATION_FRAME.validAt,
      availableTo: REAL_OVATION_FRAME.validAt,
      frameCount: 1,
      coverageComplete: false,
      noDataIntervals: [],
      selection: "history uses only forecast-valid time",
      staleAfterMinutes: 12,
      forecastLead: "carried per frame from NOAA Forecast Time minus Observation Time",
    },
    display: {
      defaultMode: "smooth",
      nativeModeAvailable: true,
      smoothing: "spatial bilinear presentation only",
      hemispheres: ["north", "south"],
    },
    frames: [frame],
    limitations: [],
  };
}

/** Native row index for a whole-degree latitude. */
export function latitudeRow(latitudeDeg: number): number {
  return (latitudeDeg - REAL_OVATION_FRAME.latitudeStartDeg) / REAL_OVATION_FRAME.latitudeStepDeg;
}
