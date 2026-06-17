export function resolveServerApiBaseUrl(): string {
  return (process.env.SLICE_STUDIO_API_URL || process.env.NEXT_PUBLIC_SLICE_STUDIO_API_URL || "http://127.0.0.1:4110").replace(/\/+$/, "");
}

export async function serverApiGet<T>(path: string, cookie: string): Promise<T> {
  const response = await fetch(`${resolveServerApiBaseUrl()}${path}`, {
    headers: { cookie },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}
