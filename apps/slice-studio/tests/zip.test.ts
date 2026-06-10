import { describe, expect, it } from "vitest";
import { createZipBuffer } from "../shared/zip";

describe("zip writer", () => {
  it("writes local file entries", () => {
    const zip = createZipBuffer([
      { name: "manifest.json", data: Buffer.from("{}") },
      { name: "slices/page_0001/slice_0001.png", data: Buffer.from("png") }
    ]);
    expect(readZipEntryNames(zip)).toEqual(["manifest.json", "slices/page_0001/slice_0001.png"]);
  });

  it("marks utf8 filenames", () => {
    const zip = createZipBuffer([
      { name: "originals/P1-首页.png", data: Buffer.from("png") }
    ]);
    expect(readZipEntryNames(zip)).toEqual(["originals/P1-首页.png"]);
    expect(zip.readUInt16LE(6) & 0x0800).toBe(0x0800);
  });
});

function readZipEntryNames(buffer: Buffer): string[] {
  const names: string[] = [];
  let offset = 0;
  while (offset < buffer.length - 4) {
    if (buffer.readUInt32LE(offset) !== 0x04034b50) break;
    const compressedSize = buffer.readUInt32LE(offset + 18);
    const nameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    names.push(buffer.subarray(offset + 30, offset + 30 + nameLength).toString("utf8"));
    offset += 30 + nameLength + extraLength + compressedSize;
  }
  return names;
}
