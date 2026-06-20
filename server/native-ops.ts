// Load native pixel-ops addon with platform detection and fallback.
// In production, the .node file is built by CI and placed alongside this file.
// For local dev, bun runs the platform-specific file directly.

type NativeOps = {
  clearAlphaRect(targetData: Buffer, width: number, height: number, bboxX: number, bboxY: number, bboxW: number, bboxH: number): Buffer;
  dilateTextMask(mask: Buffer, width: number, height: number, radius: number): Buffer;
  inpaintTextMask(targetData: Buffer, width: number, height: number, rectLeft: number, rectTop: number, rectWidth: number, rectHeight: number, maskData: Buffer, fallbackR: number, fallbackG: number, fallbackB: number): Buffer;
  alphaContentBbox(data: Buffer, width: number, height: number): number[] | null;
  applyShapeCutout(sourceData: Buffer, width: number, height: number, mode: string | null, targetLeft: number | null, targetTop: number | null, targetWidth: number | null, targetHeight: number | null): Buffer;
  pointInsideRoundedRect(localX: number, localY: number, width: number, height: number, radius: number): boolean;
};

let native: NativeOps | null = null;

function resolveNativePath(): string | null {
  const candidates = [
    "native/pixel-ops/pixel-ops.darwin-arm64.node",
    "native/pixel-ops/pixel-ops.darwin-x64.node",
    "native/pixel-ops/pixel-ops.linux-x64-gnu.node",
    "native/pixel-ops/pixel-ops.win32-x64-msvc.node",
    "server/pixel-ops.node"
  ];
  for (const candidate of candidates) {
    try {
      require.resolve(candidate);
      return candidate;
    } catch {
      // continue
    }
  }
  return null;
}

try {
  const nativePath = resolveNativePath();
  if (nativePath) {
    native = require(nativePath) as NativeOps;
  }
} catch {
  native = null;
}

export const nativePixelOps = native;
