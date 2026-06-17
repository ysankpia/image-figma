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

describe("storage adapter", () => {
  it("builds stable project storage keys", () => {
    const { storage } = makeStorage();
    expect(storage.projectOriginalImageKey("user_1", "project_1", "page_0001")).toBe("users/user_1/projects/project_1/originals/page_0001.png");
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
    storage.write(storage.assetsZipKey("user_1", "project_1"), Buffer.from("zip-data"));

    expect(storage.read(storage.projectOriginalImageKey("user_1", "project_1", "page_0001")).toString("utf8")).toBe("png-data");
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

  it("resolves fallback legacy keys for existing local projects", () => {
    const { storage } = makeStorage();
    storage.write("projects/project_1/originals/page_0001.png", Buffer.from("legacy-png"));
    expect(storage.firstExistingKey(storage.projectOriginalImageKeyVariants("user_1", "project_1", "page_0001"))).toBe("projects/project_1/originals/page_0001.png");
  });
});
