import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { createLocalStorageAdapter } from "../server/storage";

const tempRoots: string[] = [];

afterEach(() => {
  while (tempRoots.length) {
    fs.rmSync(tempRoots.pop()!, { recursive: true, force: true });
  }
});

function makeStorage() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "slice-storage-test-"));
  tempRoots.push(root);
  return { root, storage: createLocalStorageAdapter(root) };
}

function testFileBody(filePath: string, range?: { start: number; end: number }): BodyInit {
  const bytes = fs.readFileSync(filePath);
  const sliced = range ? bytes.subarray(range.start, range.end + 1) : bytes;
  return new Uint8Array(sliced);
}

describe("storage adapter", () => {
  it("builds stable project storage keys", () => {
    const { storage } = makeStorage();
    expect(storage.projectOriginalImageKey("user_1", "project_1", "page_0001")).toBe("users/user_1/projects/project_1/originals/page_0001.png");
    expect(storage.projectThumbnailImageKey("user_1", "project_1", "page_0001")).toBe("users/user_1/projects/project_1/thumbnails/page_0001.png");
    expect(storage.assetsZipKey("user_1", "project_1")).toBe("users/user_1/projects/project_1/exports/assets.zip");
    expect(storage.projectZipKey("user_1", "project_1")).toBe("users/user_1/projects/project_1/exports/project.zip");
    expect(storage.projectPageZipKey("user_1", "project_1", "page_0002")).toBe("users/user_1/projects/project_1/exports/pages/page_0002/project.zip");
    expect(storage.projectOriginalImageKeyVariants("user_1", "project_1", "page_0001")).toEqual([
      "users/user_1/projects/project_1/originals/page_0001.png",
      "projects/project_1/originals/page_0001.png"
    ]);
  });

  it("keeps keys inside the configured root", () => {
    const { storage } = makeStorage();
    expect(() => storage.absolutePath("../escape.txt")).toThrow("Invalid path");
  });

  it("writes and reads project files through keys", () => {
    const { root, storage } = makeStorage();
    storage.ensureProjectDirectories("user_1", "project_1");
    storage.write(storage.projectOriginalImageKey("user_1", "project_1", "page_0001"), Buffer.from("png-data"));
    storage.write(storage.projectThumbnailImageKey("user_1", "project_1", "page_0001"), Buffer.from("thumb-data"));
    storage.write(storage.assetsZipKey("user_1", "project_1"), Buffer.from("zip-data"));

    expect(storage.read(storage.projectOriginalImageKey("user_1", "project_1", "page_0001")).toString("utf8")).toBe("png-data");
    expect(storage.read(storage.projectThumbnailImageKey("user_1", "project_1", "page_0001")).toString("utf8")).toBe("thumb-data");
    expect(storage.read(storage.assetsZipKey("user_1", "project_1")).toString("utf8")).toBe("zip-data");
    expect(storage.exists(storage.assetsZipKey("user_1", "project_1"))).toBe(true);
    expect(storage.size(storage.assetsZipKey("user_1", "project_1"))).toBe(8);
    expect(storage.absolutePath(storage.projectOriginalImageKey("user_1", "project_1", "page_0001"))).toBe(path.join(root, "users/user_1/projects/project_1/originals/page_0001.png"));
  });

  it("returns a 404 response error when a requested file is missing", () => {
    const { storage } = makeStorage();
    expect(() => storage.response("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      notFoundMessage: "project.zip has not been generated"
    })).toThrow("project.zip has not been generated");
  });

  it("creates signed download urls for stored files", () => {
    const { storage } = makeStorage();
    const url = storage.downloadUrl("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      contentDisposition: 'attachment; filename="project.zip"'
    });
    expect(url.startsWith("/api/storage-download?token=")).toBe(true);
  });

  it("streams stored files with length and range headers", async () => {
    const { storage } = makeStorage();
    storage.write("users/user_1/projects/project_1/exports/project.zip", Buffer.from("0123456789"));

    const full = storage.response("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      fileBody: testFileBody
    });
    expect(full.status).toBe(200);
    expect(full.headers.get("accept-ranges")).toBe("bytes");
    expect(full.headers.get("content-length")).toBe("10");
    expect(await full.text()).toBe("0123456789");

    const partial = storage.response("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      range: "bytes=2-5",
      fileBody: testFileBody
    });
    expect(partial.status).toBe(206);
    expect(partial.headers.get("content-length")).toBe("4");
    expect(partial.headers.get("content-range")).toBe("bytes 2-5/10");
    expect(await partial.text()).toBe("2345");

    const suffix = storage.response("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      range: "bytes=-4",
      fileBody: testFileBody
    });
    expect(suffix.status).toBe(206);
    expect(suffix.headers.get("content-range")).toBe("bytes 6-9/10");
    expect(await suffix.text()).toBe("6789");

    const unsatisfiable = storage.response("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      range: "bytes=20-30",
      fileBody: testFileBody
    });
    expect(unsatisfiable.status).toBe(416);
    expect(unsatisfiable.headers.get("content-range")).toBe("bytes */10");
    expect(unsatisfiable.headers.get("content-length")).toBe("0");
  });

  it("resolves fallback legacy keys for existing local projects", () => {
    const { storage } = makeStorage();
    storage.write("projects/project_1/originals/page_0001.png", Buffer.from("legacy-png"));
    expect(storage.firstExistingKey(storage.projectOriginalImageKeyVariants("user_1", "project_1", "page_0001"))).toBe("projects/project_1/originals/page_0001.png");
  });
});
