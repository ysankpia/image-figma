import Link from "next/link";
import { redirect } from "next/navigation";
import { fetchCurrentUser } from "@/app/server-auth";
import { serverApiGet } from "@/app/server-api";

export default async function AdminPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");
  if (user.role !== "admin") redirect("/projects");

  const { headers } = await import("next/headers");
  const cookie = (await headers()).get("cookie") || "";
  const data = await serverApiGet<{ totals: { users: number; projects: number; pages: number; slices: number; usageEvents: number; paymentOrders: number; pendingPaymentOrders: number; paidPaymentOrders: number; paymentEvents: number } }>("/api/admin/overview", cookie);

  return (
    <main className="accountShell">
      <nav className="accountNav">
        <Link href="/projects">项目</Link>
        <Link href="/settings">设置</Link>
        <Link href="/billing">账单</Link>
      </nav>
      <section className="accountPanel">
        <p className="eyebrow">Admin</p>
        <h1>系统概览</h1>
        <dl className="accountFacts">
          <div><dt>用户</dt><dd>{data.totals.users}</dd></div>
          <div><dt>项目</dt><dd>{data.totals.projects}</dd></div>
          <div><dt>页面</dt><dd>{data.totals.pages}</dd></div>
          <div><dt>切图</dt><dd>{data.totals.slices}</dd></div>
          <div><dt>用量事件</dt><dd>{data.totals.usageEvents}</dd></div>
          <div><dt>支付订单</dt><dd>{data.totals.paymentOrders}</dd></div>
          <div><dt>待处理订单</dt><dd>{data.totals.pendingPaymentOrders}</dd></div>
          <div><dt>已支付订单</dt><dd>{data.totals.paidPaymentOrders}</dd></div>
          <div><dt>支付事件</dt><dd>{data.totals.paymentEvents}</dd></div>
        </dl>
      </section>
    </main>
  );
}
