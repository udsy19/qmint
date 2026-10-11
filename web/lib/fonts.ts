import { GeistMono } from "geist/font/mono";
import { GeistPixelGrid, GeistPixelSquare } from "geist/font/pixel";
import { GeistSans } from "geist/font/sans";

/**
 * All three Geist families from the official `geist` package (v1.7.2).
 * Sans: UI + prose. Mono: data, code, labels. Pixel: brand accents only —
 * Square (wordmark, section numerals, display moments) and Grid (token serials, loading motif).
 * The other Pixel cuts (Circle, Triangle, Line) are intentionally not loaded.
 */
export const fontVariables = [
  GeistSans.variable,
  GeistMono.variable,
  GeistPixelSquare.variable,
  GeistPixelGrid.variable,
].join(" ");
