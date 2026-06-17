import { headers } from "next/headers";
import { resolveServerApiBaseUrl } from "./server-api";

export async function fetchCurrentUser() {
  const headerList = await headers();
  const response = await fetch(`${resolveServerApiBaseUrl()}/api/auth/session`, {
    headers: {
      cookie: headerList.get("cookie") || ""
    },
    cache: "no-store"
  });
  if (!response.ok) return null;
  const data = await response.json() as { user: { id: string; email: string; name: string; role: string; status: string } | null };
  return data.user;
}
