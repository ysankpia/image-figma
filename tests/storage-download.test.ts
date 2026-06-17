import { describe, expect, it } from "vitest";
import { createSignedStorageDownloadUrl, resolveSignedStorageDownload } from "../server/storage-download";

describe("signed storage download urls", () => {
  it("round-trips a signed local download descriptor", () => {
    const url = createSignedStorageDownloadUrl("users/user_1/projects/project_1/exports/project.zip", {
      contentType: "application/zip",
      contentDisposition: 'attachment; filename="project.zip"',
      notFoundMessage: "project.zip has not been generated"
    }, 1_700_000_000_000);
    const token = new URL(`http://slice.test${url}`).searchParams.get("token");
    expect(token).toBeTruthy();

    const resolved = resolveSignedStorageDownload(token!, 1_700_000_300_000);
    expect(resolved).toEqual({
      key: "users/user_1/projects/project_1/exports/project.zip",
      response: {
        contentType: "application/zip",
        contentDisposition: 'attachment; filename="project.zip"',
        cacheControl: undefined,
        notFoundMessage: "project.zip has not been generated"
      }
    });
  });

  it("rejects tampered or expired tokens", () => {
    const url = createSignedStorageDownloadUrl("users/user_1/projects/project_1/exports/assets.zip", {
      contentType: "application/zip"
    }, 1_700_000_000_000);
    const token = new URL(`http://slice.test${url}`).searchParams.get("token");
    expect(token).toBeTruthy();
    expect(() => resolveSignedStorageDownload(`${token}x`, 1_700_000_001_000)).toThrow("Invalid download token");
    expect(() => resolveSignedStorageDownload(token!, 1_700_001_000_000)).toThrow("Download token expired");
  });
});
