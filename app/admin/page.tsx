import Link from "next/link";
import { redirect } from "next/navigation";
import { AdminPaymentActions } from "@/app/admin/AdminPaymentActions";
import { AdminUserActions } from "@/app/admin/AdminUserActions";
import { fetchCurrentUser } from "@/app/server-auth";
import { serverApiGet } from "@/app/server-api";

type AdminOverview = {
  totals: {
    users: number;
    projects: number;
    pages: number;
    slices: number;
    usageEvents: number;
    paymentOrders: number;
    pendingPaymentOrders: number;
    paidPaymentOrders: number;
    paymentEvents: number;
  };
};

type AdminPayments = {
  orders: Array<{
    id: string;
    user_id: string;
    user_email: string;
    provider: string;
    provider_order_id: string | null;
    plan_id: string;
    amount_cents: number;
    currency: string;
    status: string;
    checkout_url: string | null;
    created_at: string;
    updated_at: string;
  }>;
  events: Array<{
    id: string;
    order_id: string | null;
    provider: string;
    event_type: string;
    signature_valid: number;
    payload_json: string;
    created_at: string;
  }>;
};

type AdminUsers = {
  users: Array<{
    id: string;
    email: string;
    name: string;
    role: "user" | "admin";
    status: "active" | "suspended";
    created_at: string;
    updated_at: string;
    plan_id: string | null;
    entitlement_status: "free" | "trial" | "active" | "past_due" | "paused" | "canceled" | "expired" | "refunded" | "manual_grant" | null;
    ai_calls_remaining: number | null;
    exports_remaining: number | null;
    storage_mb: number | null;
    renews_at: string | null;
    project_count: number;
    page_count: number;
    storage_bytes: number;
  }>;
  plans: Array<{
    id: string;
    name: string;
    price_cents: number;
    currency: string;
  }>;
};

export default async function AdminPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");
  if (user.role !== "admin") redirect("/projects");

  const { headers } = await import("next/headers");
  const cookie = (await headers()).get("cookie") || "";
  const [data, payments, adminUsers] = await Promise.all([
    serverApiGet<AdminOverview>("/api/admin/overview", cookie),
    serverApiGet<AdminPayments>("/api/admin/payments", cookie),
    serverApiGet<AdminUsers>("/api/admin/users", cookie)
  ]);

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
      <section className="accountPanel">
        <p className="eyebrow">User Ops</p>
        <h2>用户与权益</h2>
        <div className="adminTableWrap">
          <table className="adminTable wide">
            <thead>
              <tr>
                <th>用户</th>
                <th>角色 / 状态</th>
                <th>套餐 / 权益</th>
                <th>资源使用</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {adminUsers.users.map((record) => (
                <tr key={record.id}>
                  <td>
                    <strong>{record.name}</strong>
                    <code>{record.email}</code>
                  </td>
                  <td>
                    <span>{record.role}</span>
                    <span className={`statusPill ${record.status}`}>{record.status}</span>
                  </td>
                  <td>
                    <span>{record.plan_id || "无套餐"}</span>
                    <span>{record.entitlement_status || "无权益"}</span>
                    <span>AI {record.ai_calls_remaining ?? 0} / 导出 {record.exports_remaining ?? 0} / {record.storage_mb ?? 0} MB</span>
                  </td>
                  <td>
                    <span>{record.project_count} 项目 / {record.page_count} 页面</span>
                    <span>{formatBytes(record.storage_bytes)}</span>
                  </td>
                  <td>{formatDate(record.created_at)}</td>
                  <td>
                    <AdminUserActions
                      userId={record.id}
                      currentStatus={record.status}
                      currentPlanId={record.plan_id}
                      currentEntitlementStatus={record.entitlement_status}
                      plans={adminUsers.plans}
                    />
                  </td>
                </tr>
              ))}
              {!adminUsers.users.length ? (
                <tr><td colSpan={6}>暂无用户</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section className="accountPanel">
        <p className="eyebrow">Payment Ops</p>
        <h2>最近支付订单</h2>
        <div className="adminTableWrap">
          <table className="adminTable">
            <thead>
              <tr>
                <th>订单</th>
                <th>用户</th>
                <th>套餐</th>
                <th>金额</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {payments.orders.map((order) => (
                <tr key={order.id}>
                  <td><code>{order.id}</code><span>{order.provider}</span></td>
                  <td>{order.user_email}</td>
                  <td>{order.plan_id}</td>
                  <td>{formatAmount(order.amount_cents, order.currency)}</td>
                  <td><span className={`statusPill ${order.status}`}>{order.status}</span></td>
                  <td>{formatDate(order.created_at)}</td>
                  <td><AdminPaymentActions orderId={order.id} status={order.status} /></td>
                </tr>
              ))}
              {!payments.orders.length ? (
                <tr><td colSpan={7}>暂无支付订单</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section className="accountPanel">
        <p className="eyebrow">Webhook Log</p>
        <h2>最近支付事件</h2>
        <div className="adminTableWrap">
          <table className="adminTable compact">
            <thead>
              <tr>
                <th>事件</th>
                <th>订单</th>
                <th>来源</th>
                <th>验签</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {payments.events.map((event) => (
                <tr key={event.id}>
                  <td>{event.event_type}</td>
                  <td>{event.order_id ? <code>{event.order_id}</code> : "无"}</td>
                  <td>{event.provider}</td>
                  <td>{event.signature_valid ? "通过" : "失败"}</td>
                  <td>{formatDate(event.created_at)}</td>
                </tr>
              ))}
              {!payments.events.length ? (
                <tr><td colSpan={5}>暂无支付事件</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <p className="accountNote">人工确认只用于回调丢失或支付 provider 异常后的运维修复；客户端支付返回页不会发放权益。</p>
      </section>
    </main>
  );
}

function formatAmount(amountCents: number, currency: string): string {
  return `${currency} ${(amountCents / 100).toFixed(2)}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
