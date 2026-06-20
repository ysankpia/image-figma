import { crc32 } from "node:zlib";

export type ZipFile = {
  name: string;
  data: Buffer;
};

export function createZipBuffer(files: ZipFile[]): Buffer {
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let offset = 0;
  const utf8Flag = 0x0800;

  for (const file of files) {
    const name = Buffer.from(file.name);
    const data = Buffer.isBuffer(file.data) ? file.data : Buffer.from(file.data);
    const crc = crc32(data);
    const local = Buffer.concat([
      uint32(0x04034b50), uint16(20), uint16(utf8Flag), uint16(0), uint16(0), uint16(0),
      uint32(crc), uint32(data.length), uint32(data.length), uint16(name.length), uint16(0), name, data
    ]);
    localParts.push(local);
    centralParts.push(Buffer.concat([
      uint32(0x02014b50), uint16(20), uint16(20), uint16(utf8Flag), uint16(0), uint16(0), uint16(0),
      uint32(crc), uint32(data.length), uint32(data.length), uint16(name.length), uint16(0), uint16(0),
      uint16(0), uint16(0), uint32(0), uint32(offset), name
    ]));
    offset += local.length;
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const centralOffset = offset;
  const end = Buffer.concat([
    uint32(0x06054b50), uint16(0), uint16(0), uint16(files.length), uint16(files.length),
    uint32(centralSize), uint32(centralOffset), uint16(0)
  ]);
  return Buffer.concat([...localParts, ...centralParts, end]);
}

function uint16(value: number): Buffer {
  const buffer = Buffer.alloc(2);
  buffer.writeUInt16LE(value);
  return buffer;
}

function uint32(value: number): Buffer {
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32LE(value >>> 0);
  return buffer;
}
