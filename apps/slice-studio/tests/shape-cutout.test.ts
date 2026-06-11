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

  it("keeps enclosed dark content even when it matches the outside background", () => {
    const width = 18;
    const height = 18;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 12;
      rgba[offset + 1] = 10;
      rgba[offset + 2] = 48;
      rgba[offset + 3] = 255;
    }
    for (let y = 4; y < 14; y += 1) {
      for (let x = 4; x < 14; x += 1) {
        const isBorder = x === 4 || x === 13 || y === 4 || y === 13;
        const offset = (y * width + x) * 4;
        if (isBorder) {
          rgba[offset] = 160;
          rgba[offset + 1] = 54;
          rgba[offset + 2] = 255;
        }
      }
    }

    const cutout = applyShapeCutout(rgba, width, height);
    expect(cutout[3]).toBe(0);
    expect(cutout[(8 * width + 8) * 4 + 3]).toBe(255);
  });

  it("uses surrounding context for tight shape crops and returns the requested bbox size", async () => {
    const width = 40;
    const height = 40;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 10;
      rgba[offset + 1] = 9;
      rgba[offset + 2] = 54;
      rgba[offset + 3] = 255;
    }

    const left = 10;
    const top = 10;
    const right = 29;
    const bottom = 25;
    const radius = 5;
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        const innerX = x < left + radius ? left + radius : x > right - radius ? right - radius : x;
        const innerY = y < top + radius ? top + radius : y > bottom - radius ? bottom - radius : y;
        const dx = x - innerX;
        const dy = y - innerY;
        const inside = dx * dx + dy * dy <= radius * radius;
        if (!inside) continue;
        const offset = (y * width + x) * 4;
        rgba[offset] = 14;
        rgba[offset + 1] = 12;
        rgba[offset + 2] = 62;
        if (x <= left + 1 || x >= right - 1 || y <= top + 1 || y >= bottom - 1) {
          rgba[offset] = 136;
          rgba[offset + 1] = 42;
          rgba[offset + 2] = 250;
        }
      }
    }

    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();
    const png = await cropSliceToPng(source, {
      cutMode: "shape",
      bbox: { x: left, y: top, width: right - left + 1, height: bottom - top + 1 }
    });
    const result = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });

    expect(result.info.width).toBe(right - left + 1);
    expect(result.info.height).toBe(bottom - top + 1);
    expect(result.data[3]).toBe(0);
    expect(result.data[(8 * result.info.width + 10) * 4 + 3]).toBe(255);
  });

  it("does not let outside background flood through large image-card interiors", async () => {
    const width = 180;
    const height = 140;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 250;
      rgba[offset + 1] = 248;
      rgba[offset + 2] = 242;
      rgba[offset + 3] = 255;
    }

    const card = { left: 28, top: 24, right: 151, bottom: 115 };
    const radius = 14;
    for (let y = card.top; y <= card.bottom; y += 1) {
      for (let x = card.left; x <= card.right; x += 1) {
        const innerX = x < card.left + radius ? card.left + radius : x > card.right - radius ? card.right - radius : x;
        const innerY = y < card.top + radius ? card.top + radius : y > card.bottom - radius ? card.bottom - radius : y;
        const dx = x - innerX;
        const dy = y - innerY;
        if (dx * dx + dy * dy > radius * radius) continue;
        const offset = (y * width + x) * 4;
        rgba[offset] = 246;
        rgba[offset + 1] = 244;
        rgba[offset + 2] = 236;
      }
    }

    // Internal content resembles the outside background and would be removed by
    // pure color-threshold flood fill if the card interior were not protected.
    for (let y = 70; y < 98; y += 1) {
      for (let x = 36; x < 112; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 251;
        rgba[offset + 1] = 249;
        rgba[offset + 2] = 243;
      }
    }

    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();
    const png = await cropSliceToPng(source, {
      cutMode: "shape",
      bbox: { x: card.left, y: card.top, width: card.right - card.left + 1, height: card.bottom - card.top + 1 }
    });
    const result = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });

    const centerOffset = (58 * result.info.width + 44) * 4;
    const cornerOffset = 0;
    expect(result.data[centerOffset + 3]).toBe(255);
    expect(result.data[cornerOffset + 3]).toBe(0);
  });
});
