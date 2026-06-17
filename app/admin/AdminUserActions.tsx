"use client";

import { useMemo, useState } from "react";
import { apiPatch } from "@/components/api";

type Plan = {
  id: string;
  name: string;
  price_cents: number;
  currency: string;
};

type EntitlementStatus =
  | "free"
  | "trial"
  | "active"
  | "past_due"
  | "paused"
  | "canceled"
  | "expired"
  | "refunded"
  | "manual_grant";

const entitlementStatuses: EntitlementStatus[] = [
  "free",
  "trial",
  "active",
  "past_due",
  "paused",
  "canceled",
  "expired",
  "refunded",
  "manual_grant"
];

export function AdminUserActions(input: {
  userId: string;
  currentStatus: "active" | "suspended";
  currentPlanId: string | null;
  currentEntitlementStatus: EntitlementStatus | null;
  plans: Plan[];
}) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [planId, setPlanId] = useState(input.currentPlanId || input.plans[0]?.id || "free");
  const [entitlementStatus, setEntitlementStatus] = useState<EntitlementStatus>(input.currentEntitlementStatus || "free");

  const nextUserStatus = useMemo(
    () => (input.currentStatus === "active" ? "suspended" : "active"),
    [input.currentStatus]
  );

  async function toggleUserStatus() {
    if (busy) return;
    setBusy(true);
    setMessage("正在更新用户状态...");
    try {
      await apiPatch(`/api/admin/users/${input.userId}/status`, { status: nextUserStatus });
      setMessage("状态已更新，刷新后可见。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveEntitlement() {
    if (busy) return;
    setBusy(true);
    setMessage("正在更新权益...");
    try {
      await apiPatch(`/api/admin/users/${input.userId}/entitlement`, {
        planId,
        status: entitlementStatus
      });
      setMessage("权益已更新，刷新后可见。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="adminUserAction">
      <button type="button" onClick={() => void toggleUserStatus()} disabled={busy}>
        {input.currentStatus === "active" ? "暂停账号" : "恢复账号"}
      </button>
      <div className="adminInlineForm">
        <select value={planId} onChange={(event) => setPlanId(event.target.value)} disabled={busy}>
          {input.plans.map((plan) => (
            <option key={plan.id} value={plan.id}>
              {plan.name} {plan.price_cents ? `(${(plan.price_cents / 100).toFixed(2)} ${plan.currency})` : "(free)"}
            </option>
          ))}
        </select>
        <select value={entitlementStatus} onChange={(event) => setEntitlementStatus(event.target.value as EntitlementStatus)} disabled={busy}>
          {entitlementStatuses.map((status) => (
            <option key={status} value={status}>{status}</option>
          ))}
        </select>
        <button type="button" onClick={() => void saveEntitlement()} disabled={busy || !planId}>
          更新权益
        </button>
      </div>
      {message ? <span>{message}</span> : null}
    </div>
  );
}
