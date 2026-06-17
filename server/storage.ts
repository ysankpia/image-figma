import fs from "node:fs";
import path from "node:path";
import { storageRoot } from "./config";
import { httpError } from "./errors";
import { createSignedStorageDownloadUrl, type StorageDownloadOptions } from "./storage-download";
import { assertInside } from "./utils";

export function createLocalStorageAdapter(root: string) {
  function normalizeKey(key: string): string {
    return String(key || "").replace(/^\/+/, "");
  }

  function absolutePath(key: string): string {
    const resolved = path.join(root, normalizeKey(key));
    assertInside(root, resolved);
    return resolved;
  }

  function ensureParentDirectory(key: string): string {
    const filePath = absolutePath(key);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    return filePath;
  }

  function projectRootKey(projectId: string): string {
    return `projects/${projectId}`;
  }

  function projectOriginalImageKey(projectId: string, pageId: string): string {
    return `${projectRootKey(projectId)}/originals/${pageId}.png`;
  }

  function assetsZipKey(projectId: string): string {
    return `${projectRootKey(projectId)}/exports/assets.zip`;
  }

  function projectZipKey(projectId: string): string {
    return `${projectRootKey(projectId)}/exports/project.zip`;
  }

  function projectPageZipKey(projectId: string, pageId: string): string {
    return `${projectRootKey(projectId)}/exports/pages/${pageId}/project.zip`;
  }

  return {
    root,
    absolutePath,
    projectRootKey,
    projectOriginalImageKey,
    assetsZipKey,
    projectZipKey,
    projectPageZipKey,
    ensureProjectDirectories(projectId: string): void {
      fs.mkdirSync(absolutePath(`${projectRootKey(projectId)}/originals`), { recursive: true });
      fs.mkdirSync(absolutePath(`${projectRootKey(projectId)}/exports`), { recursive: true });
    },
    deleteProject(projectId: string): void {
      fs.rmSync(absolutePath(projectRootKey(projectId)), { recursive: true, force: true });
    },
    exists(key: string): boolean {
      return fs.existsSync(absolutePath(key));
    },
    read(key: string, notFoundMessage = "Storage object not found"): Buffer {
      const filePath = absolutePath(key);
      if (!fs.existsSync(filePath)) throw httpError(404, notFoundMessage);
      return fs.readFileSync(filePath);
    },
    write(key: string, data: Uint8Array | Buffer): void {
      fs.writeFileSync(ensureParentDirectory(key), data);
    },
    rename(fromKey: string, toKey: string): void {
      const fromPath = absolutePath(fromKey);
      const toPath = ensureParentDirectory(toKey);
      fs.renameSync(fromPath, toPath);
    },
    remove(key: string): void {
      fs.rmSync(absolutePath(key), { force: true });
    },
    size(key: string): number {
      const stat = fs.existsSync(absolutePath(key)) ? fs.statSync(absolutePath(key)) : null;
      return stat?.isFile() ? stat.size : 0;
    },
    response(key: string, input: {
      contentType: string;
      contentDisposition?: string;
      cacheControl?: string;
      notFoundMessage?: string;
    }): Response {
      const filePath = absolutePath(key);
      if (!fs.existsSync(filePath)) throw httpError(404, input.notFoundMessage || "Storage object not found");
      const headers: Record<string, string> = {
        "content-type": input.contentType
      };
      if (input.contentDisposition) headers["content-disposition"] = input.contentDisposition;
      if (input.cacheControl) headers["cache-control"] = input.cacheControl;
      return new Response(Bun.file(filePath), { headers });
    },
    downloadUrl(key: string, input: StorageDownloadOptions): string {
      return createSignedStorageDownloadUrl(key, input);
    }
  };
}

export const storage = createLocalStorageAdapter(storageRoot);
