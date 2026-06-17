"use client";

import { useState } from "react";
import { apiPost } from "@/components/api";

export function AdminPaymentActions({ orderId, status }: { orderId: string; status: string }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const canRepair = status !== "paid" && status !== "refunded" && status !== "closed";

  async function markPaid() {
    if (!canRepair || busy) return;
    setBusy(true);
    setMessage("正在确认...");
    try {
      await apiPost(`/api/admin/payment-orders/${orderId}/mark-paid`, {});
      setMessage("已确认，刷新后可见最新状态");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="adminPaymentAction">
      <button type="button" onClick={() => void markPaid()} disabled={!canRepair || busy}>
        人工确认已支付
      </button>
      {message ? <span>{message}</span> : null}
    </div>
  );
}
