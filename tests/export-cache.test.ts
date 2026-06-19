import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  buildExportFingerprint,
  exportCacheHit,
  exportCacheKey,
  readExportSourceFile,
  writeExportCache,
  type ExportSourceFile
} from "../server/export-cache";
import { createLocalStorageAdapter } from "../server/storage";
import type { ProjectDetail } from "../shared/types";

const tempRoots: string[] = [];

afterEach(() => {
  while (tempRoots.length) {
    fs.rmSync(tempRoots.pop()!, { recursive: true, force: true });
  }
});

function makeStorage() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "slice-export-cache-test-"));
  tempRoots.push(root);
  return createLocalStorageAdapter(root);
}

function makeDetail(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    project: {
      id: "project_1",
      name: "Demo",
      createdAt: "2026-01-01T00:00:00.000Z",
      updatedAt: "2026-01-01T00:00:00.000Z",
      pageCount: 1,
      sliceCount: 1
    },
    pages: [{
      id: "page_0001",
      projectId: "project_1",
      pageIndex: 1,
      originalName: "home.png",
      displayName: "首页",
      width: 100,
      height: 80,
      sourceUrl: "/source",
      thumbnailUrl: "/thumbnail",
      slices: [{
        id: "slice_1",
        projectId: "project_1",
        pageId: "page_0001",
        sliceIndex: 1,
        name: "banner",
        kind: "image",
        cutMode: "rect",
        bbox: { x: 1, y: 2, width: 30, height: 20 },
        selected: true
      }]
    }],
    ...overrides
  };
}

function cloneDetail(detail: ProjectDetail): ProjectDetail {
  return JSON.parse(JSON.stringify(detail)) as ProjectDetail;
}

const sourceFiles: ExportSourceFile[] = [{
  pageId: "page_0001",
  key: "users/user_1/projects/project_1/originals/page_0001.png",
  size: 1234,
  mtimeMs: 4567
}];

describe("export cache", () => {
  it("builds stable fingerprints from exported content, not incidental timestamps", () => {
    const detail = makeDetail();
    const fingerprint = buildExportFingerprint({
      kind: "assets",
      exporterVersion: "test.v1",
      detail,
      sourceFiles
    });
    const timestampOnlyChange = cloneDetail(detail);
    timestampOnlyChange.project.updatedAt = "2026-01-02T00:00:00.000Z";

    expect(buildExportFingerprint({
      kind: "assets",
      exporterVersion: "test.v1",
      detail: timestampOnlyChange,
      sourceFiles
    })).toBe(fingerprint);
  });

  it("changes fingerprints when slice geometry, page naming, or source file stats change", () => {
    const detail = makeDetail();
    const fingerprint = buildExportFingerprint({
      kind: "assets",
      exporterVersion: "test.v1",
      detail,
      sourceFiles
    });
    const bboxChange = cloneDetail(detail);
    bboxChange.pages[0].slices[0].bbox.width = 31;
    const pageNameChange = cloneDetail(detail);
    pageNameChange.pages[0].displayName = "详情页";
    const sourceChange = [{ ...sourceFiles[0], mtimeMs: sourceFiles[0].mtimeMs + 1 }];

    expect(buildExportFingerprint({
      kind: "assets",
      exporterVersion: "test.v1",
      detail: bboxChange,
      sourceFiles
    })).not.toBe(fingerprint);
    expect(buildExportFingerprint({
      kind: "assets",
      exporterVersion: "test.v1",
      detail: pageNameChange,
      sourceFiles
    })).not.toBe(fingerprint);
    expect(buildExportFingerprint({
      kind: "assets",
      exporterVersion: "test.v1",
      detail,
      sourceFiles: sourceChange
    })).not.toBe(fingerprint);
  });

  it("requires both zip bytes and matching cache metadata before reusing an export", () => {
    const storage = makeStorage();
    const zipKey = storage.assetsZipKey("user_1", "project_1");
    const input = {
      zipKey,
      kind: "assets" as const,
      exporterVersion: "test.v1",
      fingerprint: "fingerprint_1",
      assetCount: 1,
      pageCount: 1
    };

    expect(exportCacheHit(input, storage)).toBe(false);
    storage.write(zipKey, Buffer.from("zip"));
    expect(exportCacheHit(input, storage)).toBe(false);
    writeExportCache(input, storage);
    expect(storage.exists(exportCacheKey(zipKey))).toBe(true);
    expect(exportCacheHit(input, storage)).toBe(true);
    expect(exportCacheHit({ ...input, fingerprint: "fingerprint_2" }, storage)).toBe(false);
    expect(exportCacheHit({ ...input, exporterVersion: "test.v2" }, storage)).toBe(false);
  });

  it("reads source file identity from the storage adapter", () => {
    const storage = makeStorage();
    const key = storage.projectOriginalImageKey("user_1", "project_1", "page_0001");
    storage.write(key, Buffer.from("original"));

    const source = readExportSourceFile("page_0001", key, storage);
    expect(source.pageId).toBe("page_0001");
    expect(source.key).toBe(key);
    expect(source.size).toBe(8);
    expect(source.mtimeMs).toBeGreaterThan(0);
  });
});
