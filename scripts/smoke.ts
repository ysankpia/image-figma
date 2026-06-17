const apiBaseUrl = process.env.SLICE_STUDIO_API_URL || "http://127.0.0.1:4110";
let sessionCookie = "";

async function main() {
  const health = await request<{ ok: true }>("/api/health");
  if (!health.ok) throw new Error("health failed");
  await assertAnonymousBlocked();
  await signUpSmokeUser();

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
              { id: "page_0001__slice_a", name: "hero", kind: "image", cutMode: "rect", bbox: { x: 1, y: 1, width: 8, height: 8 }, selected: true }
            ]
          },
          {
            pageId: "page_0002",
            slices: [
              { id: "page_0002__slice_a", name: "tab_asset", kind: "image", cutMode: "subject", bbox: { x: 3, y: 3, width: 6, height: 6 }, selected: true }
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
    if (!exported.url.startsWith("/api/storage-download?token=")) {
      throw new Error(`expected signed assets download url, got ${exported.url}`);
    }
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
    if (manifest.pages[0]?.slices[0]?.cutMode !== "subject") {
      throw new Error(`expected remaining slice cutMode subject, got ${manifest.pages[0]?.slices[0]?.cutMode}`);
    }

    const projectExport = await request<{ assetCount: number; pageCount: number; url: string }>(`/api/projects/${projectId}/export-project`, { method: "POST" });
    if (!projectExport.url.startsWith("/api/storage-download?token=")) {
      throw new Error(`expected signed project download url, got ${projectExport.url}`);
    }
    if (projectExport.assetCount !== 1) throw new Error(`expected 1 project asset, got ${projectExport.assetCount}`);
    if (projectExport.pageCount !== 2) throw new Error(`expected 2 project pages, got ${projectExport.pageCount}`);
    const projectZip = await fetch(`${apiBaseUrl}${projectExport.url}`);
    if (!projectZip.ok) throw new Error(`project.zip download failed ${projectZip.status}`);
    const projectZipBuffer = Buffer.from(await projectZip.arrayBuffer());
    const projectEntries = readZipEntryNames(projectZipBuffer);
    assertIncludes(projectEntries, "design.pen");
    assertIncludes(projectEntries, "manifest.json");
    assertIncludes(projectEntries, "project.json");
    assertIncludes(projectEntries, "assets/originals/P1-订单页.png");
    assertIncludes(projectEntries, "assets/visible/remainders/P1-订单页/remainder.png");
    assertIncludes(projectEntries, "assets/visible/slices/P1-订单页/slice_0001.png");
    const design = JSON.parse(readZipEntry(projectZipBuffer, "design.pen").toString("utf8")) as PencilDocument;
    assertPenRefsExist(design, projectEntries);
    assertEditableTextNodesUseNaturalHeight(design);
    const pencilManifest = JSON.parse(readZipEntry(projectZipBuffer, "manifest.json").toString("utf8")) as PencilManifest;
    if (pencilManifest.pencil.designPen !== "design.pen") throw new Error("pencil manifest designPen mismatch");
    if (pencilManifest.pages[0]?.remainder !== "assets/visible/remainders/P1-订单页/remainder.png") {
      throw new Error(`unexpected pencil remainder path: ${pencilManifest.pages[0]?.remainder}`);
    }
    if (pencilManifest.pages[0]?.slices[0]?.filename !== "assets/visible/slices/P1-订单页/slice_0001.png") {
      throw new Error(`unexpected pencil slice path: ${pencilManifest.pages[0]?.slices[0]?.filename}`);
    }
    const allowedOcrProviders = new Set(["baidu_ppocrv5", "tesseract"]);
    for (const [pageIndex, page] of pencilManifest.pages.entries()) {
      if (!page.ocr || !allowedOcrProviders.has(page.ocr.provider)) throw new Error(`missing pencil OCR manifest on page ${pageIndex + 1}`);
      if (typeof page.textLayerCount !== "number") throw new Error(`missing pencil textLayerCount on page ${pageIndex + 1}`);
      if (!Array.isArray(page.textLayers)) throw new Error(`missing pencil textLayers on page ${pageIndex + 1}`);
      for (const layer of page.textLayers) {
        if (typeof layer.fontWeight !== "string") throw new Error(`pencil text fontWeight must be string on page ${pageIndex + 1}`);
        if (typeof layer.fontFamily !== "string") throw new Error(`pencil text fontFamily must be string on page ${pageIndex + 1}`);
      }
    }

    console.log(JSON.stringify({ ok: true, projectId, assetCount: exported.assetCount, pages: manifest.pages.map((page) => page.pageDirectory), projectZip: true }));
  } finally {
    await request(`/api/projects/${projectId}`, { method: "DELETE" });
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchWithSession(`${apiBaseUrl}${path}`, init);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data as T;
}

async function assertAnonymousBlocked(): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/projects`);
  if (response.status !== 401) throw new Error(`anonymous project list should be blocked, got ${response.status}`);
}

async function signUpSmokeUser(): Promise<void> {
  const suffix = Date.now().toString(36);
  const response = await fetch(`${apiBaseUrl}/api/auth/sign-up`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: "Smoke User",
      email: `smoke-${suffix}@example.test`,
      password: `smoke-password-${suffix}`
    })
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`sign up failed: ${text}`);
  const cookie = response.headers.get("set-cookie")?.split(";")[0] || "";
  if (!cookie) throw new Error("sign up did not return a session cookie");
  sessionCookie = cookie;
}

async function fetchWithSession(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (sessionCookie) headers.set("cookie", sessionCookie);
  return fetch(url, { ...init, headers });
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

function assertPenRefsExist(document: PencilDocument, entries: string[]): void {
  const entrySet = new Set(entries);
  const visit = (node: PencilNode) => {
    const fill = node.fill;
    if (fill && typeof fill === "object" && fill.type === "image") {
      if (!fill.url.startsWith("./assets/visible/")) throw new Error(`bad pen image ref: ${fill.url}`);
      const entry = fill.url.slice(2);
      if (!entrySet.has(entry)) throw new Error(`missing pen image ref: ${fill.url}`);
    }
    for (const child of node.children || []) visit(child);
  };
  for (const child of document.children || []) visit(child);
}

function assertEditableTextNodesUseNaturalHeight(document: PencilDocument): void {
  const visit = (node: PencilNode) => {
    if (node.type === "text" && node.metadata?.type === "slice_studio_editable_text") {
      if (node.textGrowth !== "auto") throw new Error(`editable text must use auto growth: ${node.id}`);
      if (node.width !== undefined) throw new Error(`editable text must not set fixed width: ${node.id}`);
      if (node.height !== undefined) throw new Error(`editable text must not set fixed height: ${node.id}`);
      if (node.textAlignVertical !== undefined) throw new Error(`editable text must not vertically center: ${node.id}`);
    }
    for (const child of node.children || []) visit(child);
  };
  for (const child of document.children || []) visit(child);
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
    slices: Array<{ cutMode: string }>;
  }>;
};

type PencilManifest = {
  pencil: { designPen: string };
  pages: Array<{
    remainder: string;
    slices: Array<{ filename: string }>;
    ocr?: { provider: string; status: string; textLayerCount: number };
    textLayerCount?: number;
    textLayers?: Array<{ fontFamily?: unknown; fontWeight?: unknown }>;
  }>;
};

type PencilDocument = {
  children: PencilNode[];
};

type PencilNode = {
  id?: string;
  type?: string;
  fill?: { type: "image"; url: string } | string;
  width?: number;
  height?: number;
  textGrowth?: string;
  textAlignVertical?: string;
  metadata?: { type?: string };
  children?: PencilNode[];
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
