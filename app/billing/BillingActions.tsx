"use client";

import { useState } from "react";
import { apiPost } from "@/components/api";

export function BillingActions({ planId }: { planId: string }) {
  const [status, setStatus] = useState("");

  async function createOrder() {
    setStatus("正在创建订单...");
    try {
      const result = await apiPost<{ order: { id: string; checkoutUrl: string | null; message: string } }>("/api/billing/orders", {
        planId,
        provider: "xpay"
      });
      setStatus(`已创建订单 ${result.order.id}。${result.order.message}`);
      if (result.order.checkoutUrl) {
        window.location.href = result.order.checkoutUrl;
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "创建订单失败");
    }
  }

  return (
    <div className="billingAction">
      <button type="button" className="primaryButton" onClick={() => void createOrder()}>创建 XPay 预留订单</button>
      {status ? <span>{status}</span> : null}
    </div>
  );
}
