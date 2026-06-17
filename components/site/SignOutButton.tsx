"use client";

import { LogOut } from "lucide-react";
import { useState } from "react";
import { apiPost } from "@/components/api";

export function SignOutButton({
  label = "退出登录",
  compact = false
}: {
  label?: string;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState(false);

  async function signOut() {
    if (busy) return;
    setBusy(true);
    try {
      await apiPost("/api/auth/sign-out", {});
      window.location.href = "/";
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className={compact ? "signOutButton compact" : "signOutButton"}
      onClick={() => void signOut()}
      disabled={busy}
      aria-label={label}
    >
      <LogOut aria-hidden="true" />
      {!compact ? <span>{label}</span> : null}
    </button>
  );
}
