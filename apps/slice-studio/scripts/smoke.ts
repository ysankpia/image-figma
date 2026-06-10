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
    form.append("files", new File([png.buffer.slice(png.byteOffset, png.byteOffset + png.byteLength) as ArrayBuffer], "page.png", { type: "image/png" }));
    await request(`/api/projects/${projectId}/pages`, { method: "POST", body: form });

    await request(`/api/projects/${projectId}/slices`, {
      method: "PUT",
      body: JSON.stringify({
        pages: [{
          pageId: "page_0001",
          slices: [
            { id: "page_0001__slice_a", name: "slice_01", kind: "image", bbox: { x: 1, y: 1, width: 8, height: 8 }, selected: true }
          ]
        }]
      }),
      headers: { "content-type": "application/json" }
    });

    const exported = await request<{ assetCount: number; url: string }>(`/api/projects/${projectId}/export-assets`, { method: "POST" });
    if (exported.assetCount !== 1) throw new Error(`expected 1 asset, got ${exported.assetCount}`);
    const zip = await fetch(`${apiBaseUrl}${exported.url}`);
    if (!zip.ok) throw new Error(`zip download failed ${zip.status}`);
    console.log(JSON.stringify({ ok: true, projectId, assetCount: exported.assetCount }));
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

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
