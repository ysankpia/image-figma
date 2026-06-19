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

  function userRootKey(userId: string): string {
    return `users/${userId}`;
  }

  function projectRootKey(userId: string, projectId: string): string {
    return `${userRootKey(userId)}/projects/${projectId}`;
  }

  function legacyProjectRootKey(projectId: string): string {
    return `projects/${projectId}`;
  }

  function projectOriginalImageKey(userId: string, projectId: string, pageId: string): string {
    return `${projectRootKey(userId, projectId)}/originals/${pageId}.png`;
  }

  function projectThumbnailImageKey(userId: string, projectId: string, pageId: string): string {
    return `${projectRootKey(userId, projectId)}/thumbnails/${pageId}.png`;
  }

  function legacyProjectOriginalImageKey(projectId: string, pageId: string): string {
    return `${legacyProjectRootKey(projectId)}/originals/${pageId}.png`;
  }

  function projectOriginalImageKeyVariants(userId: string, projectId: string, pageId: string): string[] {
    return [
      projectOriginalImageKey(userId, projectId, pageId),
      legacyProjectOriginalImageKey(projectId, pageId)
    ];
  }

  function assetsZipKey(userId: string, projectId: string): string {
    return `${projectRootKey(userId, projectId)}/exports/assets.zip`;
  }

  function legacyAssetsZipKey(projectId: string): string {
    return `${legacyProjectRootKey(projectId)}/exports/assets.zip`;
  }

  function assetsZipKeyVariants(userId: string, projectId: string): string[] {
    return [
      assetsZipKey(userId, projectId),
      legacyAssetsZipKey(projectId)
    ];
  }

  function projectZipKey(userId: string, projectId: string): string {
    return `${projectRootKey(userId, projectId)}/exports/project.zip`;
  }

  function legacyProjectZipKey(projectId: string): string {
    return `${legacyProjectRootKey(projectId)}/exports/project.zip`;
  }

  function projectZipKeyVariants(userId: string, projectId: string): string[] {
    return [
      projectZipKey(userId, projectId),
      legacyProjectZipKey(projectId)
    ];
  }

  function projectPageZipKey(userId: string, projectId: string, pageId: string): string {
    return `${projectRootKey(userId, projectId)}/exports/pages/${pageId}/project.zip`;
  }

  function legacyProjectPageZipKey(projectId: string, pageId: string): string {
    return `${legacyProjectRootKey(projectId)}/exports/pages/${pageId}/project.zip`;
  }

  function projectPageZipKeyVariants(userId: string, projectId: string, pageId: string): string[] {
    return [
      projectPageZipKey(userId, projectId, pageId),
      legacyProjectPageZipKey(projectId, pageId)
    ];
  }

  function firstExistingKey(keys: string[], notFoundMessage = "Storage object not found"): string {
    for (const key of keys) {
      if (fs.existsSync(absolutePath(key))) return key;
    }
    throw httpError(404, notFoundMessage);
  }

  return {
    root,
    absolutePath,
    userRootKey,
    projectRootKey,
    legacyProjectRootKey,
    projectOriginalImageKey,
    projectThumbnailImageKey,
    projectOriginalImageKeyVariants,
    assetsZipKey,
    assetsZipKeyVariants,
    projectZipKey,
    projectZipKeyVariants,
    projectPageZipKey,
    projectPageZipKeyVariants,
    firstExistingKey,
    ensureProjectDirectories(userId: string, projectId: string): void {
      fs.mkdirSync(absolutePath(`${projectRootKey(userId, projectId)}/originals`), { recursive: true });
      fs.mkdirSync(absolutePath(`${projectRootKey(userId, projectId)}/thumbnails`), { recursive: true });
      fs.mkdirSync(absolutePath(`${projectRootKey(userId, projectId)}/exports`), { recursive: true });
    },
    deleteProject(userId: string, projectId: string): void {
      fs.rmSync(absolutePath(projectRootKey(userId, projectId)), { recursive: true, force: true });
      fs.rmSync(absolutePath(legacyProjectRootKey(projectId)), { recursive: true, force: true });
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
