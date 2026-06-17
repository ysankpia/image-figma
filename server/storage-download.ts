import crypto from "node:crypto";
import { downloadSigningSecret, downloadUrlTtlSeconds } from "./config";
import { httpError } from "./errors";

export type StorageDownloadOptions = {
  contentType: string;
  contentDisposition?: string;
  cacheControl?: string;
  notFoundMessage?: string;
};

type SignedStorageDownloadPayload = StorageDownloadOptions & {
  exp: number;
  key: string;
};

export function createSignedStorageDownloadUrl(
  key: string,
  options: StorageDownloadOptions,
  now = Date.now()
): string {
  const payload = encodePayload({
    ...options,
    key,
    exp: Math.floor(now / 1000) + downloadUrlTtlSeconds
  });
  const signature = signPayload(payload);
  return `/api/storage-download?token=${encodeURIComponent(`${payload}.${signature}`)}`;
}

export function resolveSignedStorageDownload(token: string, now = Date.now()): {
  key: string;
  response: StorageDownloadOptions;
} {
  const [payload, signature] = String(token || "").split(".");
  if (!payload || !signature) throw httpError(403, "Invalid download token");
  const expected = signPayload(payload);
  const expectedBuffer = Buffer.from(expected);
  const signatureBuffer = Buffer.from(signature);
  if (expectedBuffer.length !== signatureBuffer.length || !crypto.timingSafeEqual(expectedBuffer, signatureBuffer)) {
    throw httpError(403, "Invalid download token");
  }

  const decoded = decodePayload(payload);
  if (decoded.exp <= Math.floor(now / 1000)) throw httpError(403, "Download token expired");
  if (!decoded.key || !decoded.contentType) throw httpError(403, "Invalid download token");
  return {
    key: decoded.key,
    response: {
      contentType: decoded.contentType,
      contentDisposition: decoded.contentDisposition,
      cacheControl: decoded.cacheControl,
      notFoundMessage: decoded.notFoundMessage
    }
  };
}

function signPayload(payload: string): string {
  return crypto.createHmac("sha256", downloadSigningSecret).update(payload).digest("base64url");
}

function encodePayload(payload: SignedStorageDownloadPayload): string {
  return Buffer.from(JSON.stringify(payload)).toString("base64url");
}

function decodePayload(payload: string): SignedStorageDownloadPayload {
  try {
    const decoded = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as Partial<SignedStorageDownloadPayload>;
    return {
      key: typeof decoded.key === "string" ? decoded.key : "",
      contentType: typeof decoded.contentType === "string" ? decoded.contentType : "",
      contentDisposition: typeof decoded.contentDisposition === "string" ? decoded.contentDisposition : undefined,
      cacheControl: typeof decoded.cacheControl === "string" ? decoded.cacheControl : undefined,
      notFoundMessage: typeof decoded.notFoundMessage === "string" ? decoded.notFoundMessage : undefined,
      exp: Number.isFinite(decoded.exp) ? Number(decoded.exp) : 0
    };
  } catch {
    throw httpError(403, "Invalid download token");
  }
}
