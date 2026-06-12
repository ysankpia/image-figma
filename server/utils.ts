import path from "node:path";

export function randomHex(bytes: number): string {
  return Array.from({ length: bytes }, () => Math.floor(Math.random() * 256).toString(16).padStart(2, "0")).join("");
}

export function sanitizeName(value: unknown, fallback = "untitled"): string {
  return String(value || fallback).trim().replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80) || fallback;
}

export function sanitizeFileName(value: unknown, fallback = "source.png"): string {
  const name = path.basename(String(value || fallback)).replace(/[\\/:*?"<>|]+/g, "_").slice(0, 120);
  return name || fallback;
}

export function assertInside(root: string, target: string): void {
  const relative = path.relative(root, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("Invalid path");
  }
}
