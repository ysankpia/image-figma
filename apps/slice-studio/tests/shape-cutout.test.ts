import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { applyShapeCutout, cropSliceToPng } from "../server/shape-cutout";

describe("shape cutout", () => {
  it("removes local background and keeps foreground alpha", () => {
    const width = 10;
    const height = 10;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    for (let y = 3; y < 7; y += 1) {
      for (let x = 3; x < 7; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 0;
        rgba[offset + 1] = 0;
        rgba[offset + 2] = 0;
      }
    }

    const cutout = applyShapeCutout(rgba, width, height);
    expect(cutout[3]).toBe(0);
    expect(cutout[(5 * width + 5) * 4 + 3]).toBe(255);
  });

  it("keeps rectangular crops opaque in rect mode", async () => {
    const source = await sharp({
      create: {
        width: 8,
        height: 8,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const png = await cropSliceToPng(source, {
      cutMode: "rect",
      bbox: { x: 1, y: 1, width: 4, height: 4 }
    });
    const raw = await sharp(png).ensureAlpha().raw().toBuffer();
    expect(raw[3]).toBe(255);
  });

  it("writes transparent pixels in shape mode", async () => {
    const width = 10;
    const height = 10;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    for (let y = 3; y < 7; y += 1) {
      for (let x = 3; x < 7; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 0;
        rgba[offset + 1] = 0;
        rgba[offset + 2] = 0;
      }
    }
    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const png = await cropSliceToPng(source, {
      cutMode: "shape",
      bbox: { x: 0, y: 0, width, height }
    });
    const raw = await sharp(png).ensureAlpha().raw().toBuffer();
    expect(raw[3]).toBe(0);
    expect(raw[(5 * width + 5) * 4 + 3]).toBe(255);
  });
});
