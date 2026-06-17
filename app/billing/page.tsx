import Link from "next/link";
import { redirect } from "next/navigation";
import { fetchCurrentUser } from "@/app/server-auth";
import { serverApiGet } from "@/app/server-api";
import { BillingActions } from "./BillingActions";

type Plan = {
  id: string;
  name: string;
  monthly_ai_calls: number;
  monthly_exports: number;
  storage_mb: number;
  price_cents: number;
  currency: string;
};

export default async function BillingPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");

  const { headers } = await import("next/headers");
  const cookie = (await headers()).get("cookie") || "";
  const [me, planResponse] = await Promise.all([
    serverApiGet<{
      entitlement: {
        plan: Plan;
        entitlement: {
          status: string;
          ai_calls_remaining: number;
          exports_remaining: number;
          storage_mb: number;
          renews_at: string | null;
        };
      };
      usage: Array<{ id: string; event_type: string; quantity: number; created_at: string }>;
      paymentOrders: Array<{ id: string; plan_id: string; amount_cents: number; currency: string; status: string; created_at: string }>;
    }>("/api/me", cookie),
    serverApiGet<{ plans: Plan[] }>("/api/billing/plans", cookie)
  ]);
  const paidPlan = planResponse.plans.find((plan) => plan.price_cents > 0);

  return (
    <main className="accountShell">
      <nav className="accountNav">
        <Link href="/projects">项目</Link>
        <Link href="/settings">设置</Link>
        <Link href="/admin">管理</Link>
      </nav>
      <section className="accountPanel">
        <p className="eyebrow">Billing</p>
        <h1>额度与账单</h1>
        <dl className="accountFacts">
          <div><dt>当前计划</dt><dd>{me.entitlement.plan.name}</dd></div>
          <div><dt>状态</dt><dd>{me.entitlement.entitlement.status}</dd></div>
          <div><dt>AI 剩余额度</dt><dd>{me.entitlement.entitlement.ai_calls_remaining}</dd></div>
          <div><dt>导出剩余额度</dt><dd>{me.entitlement.entitlement.exports_remaining}</dd></div>
          <div><dt>存储上限</dt><dd>{me.entitlement.entitlement.storage_mb} MB</dd></div>
        </dl>
        {paidPlan ? <BillingActions planId={paidPlan.id} /> : null}
      </section>
      <section className="accountPanel">
        <h2>可选计划</h2>
        <div className="planGrid">
          {planResponse.plans.map((plan) => (
            <article key={plan.id} className="planCard">
              <strong>{plan.name}</strong>
              <span>{plan.price_cents ? `${(plan.price_cents / 100).toFixed(2)} ${plan.currency}` : "免费"}</span>
              <small>{plan.monthly_ai_calls} 次 AI / {plan.monthly_exports} 次导出 / {plan.storage_mb} MB</small>
            </article>
          ))}
        </div>
      </section>
      <section className="accountPanel">
        <h2>最近用量</h2>
        <div className="simpleList">
          {me.usage.length ? me.usage.map((event) => (
            <span key={event.id}>{event.event_type} x{event.quantity} · {new Date(event.created_at).toLocaleString("zh-CN")}</span>
          )) : <span>暂无用量记录。</span>}
        </div>
      </section>
      <section className="accountPanel">
        <h2>订单</h2>
        <div className="simpleList">
          {me.paymentOrders.length ? me.paymentOrders.map((order) => (
            <span key={order.id}>{order.id} · {order.plan_id} · {order.status} · {(order.amount_cents / 100).toFixed(2)} {order.currency}</span>
          )) : <span>暂无订单。</span>}
        </div>
      </section>
    </main>
  );
}
