const apiBaseUrl = process.env.SLICE_STUDIO_API_URL || "http://127.0.0.1:4110";

async function main() {
  const health = await request<{ ok: true }>("/api/health");
  if (!health.ok) throw new Error("health failed");

  const created = await request<{ project: { id: string } }>("/api/projects", {
    method: "POST",
    body: JSON.stringify({ name: "smoke-slice-studio" }),
    headers: { "content-type": "application/json" }
  });
  const projectId = created.project.id;

  try {
    const png = createTinyPng();
    const form = new FormData();
    for (const name of ["home.png", "orders.png", "checkout.png"]) {
      form.append("files", new File([arrayBufferFromBytes(png)], name, { type: "image/png" }));
    }
    await request(`/api/projects/${projectId}/pages`, { method: "POST", body: form });
    await renamePage(projectId, "page_0001", "首页");
    await renamePage(projectId, "page_0002", "订单页");
    await renamePage(projectId, "page_0003", "购买页");

    await request(`/api/projects/${projectId}/slices`, {
      method: "PUT",
      body: JSON.stringify({
        pages: [
          {
            pageId: "page_0001",
            slices: [
              { id: "page_0001__slice_a", name: "hero", kind: "image", bbox: { x: 1, y: 1, width: 8, height: 8 }, selected: true }
            ]
          },
          {
            pageId: "page_0002",
            slices: [
              { id: "page_0002__slice_a", name: "tab_icon", kind: "icon", bbox: { x: 3, y: 3, width: 6, height: 6 }, selected: true }
            ]
          },
          { pageId: "page_0003", slices: [] }
        ]
      }),
      headers: { "content-type": "application/json" }
    });

    await request(`/api/projects/${projectId}/pages/order`, {
      method: "PATCH",
      body: JSON.stringify({ pageIds: ["page_0002", "page_0001", "page_0003"] }),
      headers: { "content-type": "application/json" }
    });

    const replaceForm = new FormData();
    replaceForm.append("file", new File([arrayBufferFromBytes(png)], "home-replaced.png", { type: "image/png" }));
    const replaced = await request<ProjectDetail>(`/api/projects/${projectId}/pages/page_0001/replace`, { method: "POST", body: replaceForm });
    const replacedPage = replaced.pages.find((page) => page.id === "page_0001");
    if (!replacedPage) throw new Error("replaced page missing");
    if (replacedPage.slices.length !== 0) throw new Error("replace should clear page slices");
    if (replacedPage.originalName !== "home-replaced.png") throw new Error(`replace originalName failed: ${replacedPage.originalName}`);

    const deleted = await request<ProjectDetail>(`/api/projects/${projectId}/pages/page_0003`, { method: "DELETE" });
    if (deleted.pages.length !== 2) throw new Error(`expected 2 pages after delete, got ${deleted.pages.length}`);
    if (deleted.pages.map((page) => page.pageIndex).join(",") !== "1,2") {
      throw new Error(`page indexes not continuous: ${deleted.pages.map((page) => page.pageIndex).join(",")}`);
    }

    const exported = await request<{ assetCount: number; url: string }>(`/api/projects/${projectId}/export-assets`, { method: "POST" });
    if (exported.assetCount !== 1) throw new Error(`expected 1 asset, got ${exported.assetCount}`);
    const zip = await fetch(`${apiBaseUrl}${exported.url}`);
    if (!zip.ok) throw new Error(`zip download failed ${zip.status}`);
    const zipBuffer = Buffer.from(await zip.arrayBuffer());
    const entries = readZipEntryNames(zipBuffer);
    assertIncludes(entries, "originals/P1-订单页.png");
    assertIncludes(entries, "originals/P2-首页.png");
    assertIncludes(entries, "slices/P1-订单页/slice_0001.png");
    assertIncludes(entries, "manifest.json");
    assertIncludes(entries, "project.json");
    const manifest = JSON.parse(readZipEntry(zipBuffer, "manifest.json").toString("utf8")) as ExportManifest;
    if (manifest.pages.map((page) => page.pageDirectory).join(",") !== "P1-订单页,P2-首页") {
      throw new Error(`unexpected manifest order: ${manifest.pages.map((page) => page.pageDirectory).join(",")}`);
    }
    if (manifest.pages[0]?.slices.length !== 1 || manifest.pages[1]?.slices.length !== 0) {
      throw new Error("manifest slices do not match replace/delete flow");
    }
    console.log(JSON.stringify({ ok: true, projectId, assetCount: exported.assetCount, pages: manifest.pages.map((page) => page.pageDirectory) }));
  } finally {
    await request(`/api/projects/${projectId}`, { method: "DELETE" });
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data as T;
}

function createTinyPng(): Uint8Array {
  return Uint8Array.from(Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAAI0lEQVR42mP8z8Dwn4GKgImaho0aNmjYoGGDho0bFAAAoO0CH2pX1EAAAAAASUVORK5CYII=",
    "base64"
  ));
}

async function renamePage(projectId: string, pageId: string, displayName: string): Promise<void> {
  await request(`/api/projects/${projectId}/pages/${pageId}`, {
    method: "PATCH",
    body: JSON.stringify({ displayName }),
    headers: { "content-type": "application/json" }
  });
}

function arrayBufferFromBytes(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

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

function readZipEntry(buffer: Buffer, expectedName: string): Buffer {
  let offset = 0;
  while (offset < buffer.length - 4) {
    if (buffer.readUInt32LE(offset) !== 0x04034b50) break;
    const compressedSize = buffer.readUInt32LE(offset + 18);
    const nameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const name = buffer.subarray(offset + 30, offset + 30 + nameLength).toString("utf8");
    const dataStart = offset + 30 + nameLength + extraLength;
    if (name === expectedName) return buffer.subarray(dataStart, dataStart + compressedSize);
    offset = dataStart + compressedSize;
  }
  throw new Error(`zip entry not found: ${expectedName}`);
}

function assertIncludes(values: string[], expected: string): void {
  if (!values.includes(expected)) {
    throw new Error(`expected zip entry ${expected}, got ${values.join(", ")}`);
  }
}

type ProjectDetail = {
  pages: Array<{
    id: string;
    pageIndex: number;
    originalName: string;
    slices: unknown[];
  }>;
};

type ExportManifest = {
  pages: Array<{
    pageDirectory: string;
    slices: unknown[];
  }>;
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
