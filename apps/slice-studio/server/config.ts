import path from "node:path";

export const apiHost = process.env.SLICE_STUDIO_API_HOST || "127.0.0.1";
export const apiPort = Number(process.env.SLICE_STUDIO_API_PORT || 4110);
export const storageRoot = path.resolve(process.env.SLICE_STUDIO_STORAGE_ROOT || path.join(process.cwd(), "storage"));
export const projectsRoot = path.join(storageRoot, "projects");
export const databasePath = path.join(storageRoot, "app.sqlite");
export const publicApiBaseUrl = process.env.SLICE_STUDIO_PUBLIC_API_URL || `http://${apiHost}:${apiPort}`;
