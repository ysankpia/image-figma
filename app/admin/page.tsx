import { redirect } from "next/navigation";
import { AdminPaymentActions } from "@/app/admin/AdminPaymentActions";
import { AdminUserActions } from "@/app/admin/AdminUserActions";
import { fetchCurrentUser } from "@/app/server-auth";
import { serverApiGet } from "@/app/server-api";
import { ProductConsoleShell } from "@/components/site/ProductConsoleShell";

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
  const visibleUsers = adminUsers.users.slice(0, 12);
  const visibleOrders = payments.orders.slice(0, 8);
  const visibleEvents = payments.events.slice(0, 8);
  const activeUsers = adminUsers.users.filter((record) => record.status === "active").length;
  const paidUsers = adminUsers.users.filter((record) => {
    return record.entitlement_status === "active" || record.entitlement_status === "manual_grant";
  }).length;

  return (
    <ProductConsoleShell
      user={user}
      active="admin"
      eyebrow="Admin"
      title="管理后台"
      description="这页先服务真实运营：看项目规模、手动纠偏用户权益、检查历史订单和支付事件。支付接入暂停，不再把它当当前重点。"
      footerNote="用户表默认只展示最近 12 个账号，避免调试账号把整页冲成长报表。需要更深运营动作时，再补筛选、搜索和审计流。"
    >
      <section className="consoleSection">
        <div className="sectionSplit dashboardTopSplit">
          <div className="sectionHeader">
            <div>
              <h2>运行概览</h2>
              <p>直接看用户、项目、页面、切图和支付占位数据，不再让页面从上到下全是原始表格。</p>
            </div>
          </div>
          <div className="toolSurface summarySurface">
            <div className="summaryRows">
              <div>
                <span>活跃账号</span>
                <strong>{activeUsers}</strong>
              </div>
              <div>
                <span>已开通权益</span>
                <strong>{paidUsers}</strong>
              </div>
              <div>
                <span>待修支付</span>
                <strong>{data.totals.pendingPaymentOrders}</strong>
              </div>
            </div>
          </div>
        </div>
        <dl className="metricGrid metricGridCompact">
          <div className="metricCard"><dt>用户</dt><dd>{data.totals.users}</dd></div>
          <div className="metricCard"><dt>项目</dt><dd>{data.totals.projects}</dd></div>
          <div className="metricCard"><dt>页面</dt><dd>{data.totals.pages}</dd></div>
          <div className="metricCard"><dt>切图</dt><dd>{data.totals.slices}</dd></div>
          <div className="metricCard"><dt>用量事件</dt><dd>{data.totals.usageEvents}</dd></div>
          <div className="metricCard"><dt>支付订单</dt><dd>{data.totals.paymentOrders}</dd></div>
          <div className="metricCard"><dt>待处理订单</dt><dd>{data.totals.pendingPaymentOrders}</dd></div>
          <div className="metricCard"><dt>支付事件</dt><dd>{data.totals.paymentEvents}</dd></div>
        </dl>
      </section>

      <section className="consoleSection">
        <div className="calloutSurface emphasis">
          <strong>当前重点</strong>
          <p>先把账号归属、额度、导出和管理纠偏流程做顺。支付接入暂缓，后续再接链动小铺或新的 provider。</p>
        </div>
      </section>

      <section className="consoleSection">
        <div className="sectionHeader">
          <div>
            <h2>用户与权益</h2>
            <p>展示最近 {visibleUsers.length} 个账号。先保留最关键的套餐、额度、资源规模和人工纠偏动作。</p>
          </div>
          <span className="sectionMeta">总计 {adminUsers.users.length} 个账号</span>
        </div>
        <div className="tableSurface denseTableSurface">
          <div className="adminTableWrap">
            <table className="adminTable wide modern">
              <thead>
                <tr>
                  <th>用户</th>
                  <th>套餐与额度</th>
                  <th>资源使用</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {visibleUsers.map((record) => (
                  <tr key={record.id}>
                    <td>
                      <div className="cellStack">
                        <strong>{record.name}</strong>
                        <code>{record.email}</code>
                        <span>{formatDate(record.created_at)}</span>
                      </div>
                    </td>
                    <td>
                      <div className="cellStack">
                        <strong>{record.plan_id || "无套餐"}</strong>
                        <span>{entitlementLabel(record.entitlement_status)}</span>
                        <span>AI {record.ai_calls_remaining ?? 0} / 导出 {record.exports_remaining ?? 0} / {record.storage_mb ?? 0} MB</span>
                      </div>
                    </td>
                    <td>
                      <div className="cellStack">
                        <strong>{record.project_count} 项目 / {record.page_count} 页面</strong>
                        <span>{formatBytes(record.storage_bytes)}</span>
                      </div>
                    </td>
                    <td>
                      <div className="cellStack">
                        <span className="statusPill neutral">{record.role === "admin" ? "管理员" : "普通用户"}</span>
                        <span className={`statusPill ${record.status}`}>{record.status === "active" ? "正常" : "已暂停"}</span>
                      </div>
                    </td>
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
                {!visibleUsers.length ? (
                  <tr><td colSpan={5}>暂无用户</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="consoleSection">
        <div className="sectionSplit">
          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>历史支付订单</h2>
                <p>支付现在先不推进，但历史订单和人工纠偏入口保留，避免彻底断档。</p>
              </div>
            </div>
            <div className="adminTableWrap">
              <table className="adminTable modern">
                <thead>
                  <tr>
                    <th>订单</th>
                    <th>用户</th>
                    <th>金额</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleOrders.map((order) => (
                    <tr key={order.id}>
                      <td>
                        <div className="cellStack">
                          <code>{order.id}</code>
                          <span>{order.provider} / {order.plan_id.toUpperCase()}</span>
                        </div>
                      </td>
                      <td>{order.user_email}</td>
                      <td>{formatAmount(order.amount_cents, order.currency)}</td>
                      <td><span className={`statusPill ${order.status}`}>{orderStatusLabel(order.status)}</span></td>
                      <td><AdminPaymentActions orderId={order.id} status={order.status} /></td>
                    </tr>
                  ))}
                  {!visibleOrders.length ? (
                    <tr><td colSpan={5}>暂无支付订单</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>最近支付事件</h2>
                <p>只看最近事件。正式支付恢复后，再把筛选和详情抽屉补上。</p>
              </div>
            </div>
            <div className="activityList">
              {visibleEvents.length ? visibleEvents.map((event) => (
                <div key={event.id} className="activityRow stacked">
                  <div>
                    <strong>{event.event_type}</strong>
                    <span>{event.provider}</span>
                  </div>
                  <div>
                    <span>{event.order_id || "无订单"}</span>
                    <time>{formatDate(event.created_at)}</time>
                  </div>
                  <span className={event.signature_valid ? "statusPill paid" : "statusPill failed"}>
                    {event.signature_valid ? "验签通过" : "验签失败"}
                  </span>
                </div>
              )) : <span className="emptyInline">暂无支付事件。</span>}
            </div>
          </div>
        </div>
      </section>
    </ProductConsoleShell>
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

function entitlementLabel(status: AdminUsers["users"][number]["entitlement_status"]): string {
  if (status === "free") return "免费";
  if (status === "trial") return "试用";
  if (status === "active") return "已开通";
  if (status === "manual_grant") return "人工开通";
  if (status === "paused") return "已暂停";
  if (status === "canceled") return "已取消";
  if (status === "expired") return "已过期";
  if (status === "refunded") return "已退款";
  if (status === "past_due") return "待补款";
  return status || "无权益";
}

function orderStatusLabel(status: string): string {
  if (status === "pending") return "待处理";
  if (status === "paid") return "已支付";
  if (status === "failed") return "失败";
  if (status === "closed") return "已关闭";
  if (status === "refunded") return "已退款";
  return status;
}
