// Implements design.md section 16: WCAG 2.x contrast ratio and tint compositing.
// Pure functions, no DOM.

const MAX_CHANNEL = 255;
const LINEAR_THRESHOLD = 0.03928;
const LINEAR_DIVISOR = 12.92;
const GAMMA_OFFSET = 0.055;
const GAMMA_DIVISOR = 1.055;
const GAMMA_EXPONENT = 2.4;
const LUMA_RED = 0.2126;
const LUMA_GREEN = 0.7152;
const LUMA_BLUE = 0.0722;
const RATIO_OFFSET = 0.05;
const HEX_RGB = /^#[0-9a-fA-F]{6}$/;
const HEX_RGBA = /^#[0-9a-fA-F]{8}$/;

function channelAt(hex: string, index: number): number {
  const start = 1 + index * 2;
  return Number.parseInt(hex.slice(start, start + 2), 16);
}

function linearise(value: number): number {
  const c = value / MAX_CHANNEL;
  return c <= LINEAR_THRESHOLD
    ? c / LINEAR_DIVISOR
    : ((c + GAMMA_OFFSET) / GAMMA_DIVISOR) ** GAMMA_EXPONENT;
}

function toHex(value: number): string {
  return value.toString(16).padStart(2, '0');
}

export function relativeLuminance(hex: string): number {
  if (!HEX_RGB.test(hex)) {
    throw new Error(`Invalid #rrggbb colour: ${hex}`);
  }
  return (
    LUMA_RED * linearise(channelAt(hex, 0)) +
    LUMA_GREEN * linearise(channelAt(hex, 1)) +
    LUMA_BLUE * linearise(channelAt(hex, 2))
  );
}

export function contrastRatio(fgHex: string, bgHex: string): number {
  const first = relativeLuminance(fgHex);
  const second = relativeLuminance(bgHex);
  return (Math.max(first, second) + RATIO_OFFSET) / (Math.min(first, second) + RATIO_OFFSET);
}

export function compositeOver(fgRgba: string, bgHex: string): string {
  if (!HEX_RGBA.test(fgRgba)) {
    throw new Error(`Invalid #rrggbbaa colour: ${fgRgba}`);
  }
  if (!HEX_RGB.test(bgHex)) {
    throw new Error(`Invalid #rrggbb colour: ${bgHex}`);
  }
  const alpha = channelAt(fgRgba, 3) / MAX_CHANNEL;
  const mixed = [0, 1, 2].map((i) =>
    Math.round(alpha * channelAt(fgRgba, i) + (1 - alpha) * channelAt(bgHex, i)),
  );
  return `#${mixed.map(toHex).join('')}`;
}
