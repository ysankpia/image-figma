import { redirect } from "next/navigation";
import { fetchCurrentUser } from "@/app/server-auth";
import { serverApiGet } from "@/app/server-api";
import { ProductConsoleShell } from "@/components/site/ProductConsoleShell";
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
      accountUsage: { projectCount: number; pageCount: number; storageBytes: number };
      usage: Array<{ id: string; event_type: string; quantity: number; created_at: string }>;
      paymentOrders: Array<{ id: string; plan_id: string; amount_cents: number; currency: string; status: string; created_at: string }>;
    }>("/api/me", cookie),
    serverApiGet<{ plans: Plan[] }>("/api/billing/plans", cookie)
  ]);
  const paidPlan = planResponse.plans.find((plan) => plan.price_cents > 0);
  const recentUsage = me.usage.slice(0, 8);
  const recentOrders = me.paymentOrders.slice(0, 8);

  return (
    <ProductConsoleShell
      user={user}
      active="billing"
      eyebrow="Billing"
      title="额度与账单"
      description="这一页先服务真实使用：看当前套餐、剩余额度、项目规模和历史订单。支付接入暂缓，不再把半成品 checkout 当主入口。"
      footerNote="当前订单记录仍然保留，主要用于后续对账和迁移。真正的购买链路会在新支付方案就绪后重新接入。"
    >
      <section className="consoleSection">
        <div className="calloutSurface emphasis">
          <strong>当前策略</strong>
          <p>账单页先承担两个职责：让用户看清额度和历史记录，让产品后续能够无缝接回新的支付 provider。现在不再暴露半成品支付入口。</p>
        </div>
      </section>

      <section className="consoleSection">
        <div className="sectionHeader">
          <div>
            <h2>当前额度</h2>
            <p>账号可用状态、资源上限和工作区规模在这里一次看清。</p>
          </div>
        </div>
        <dl className="metricGrid metricGridCompact">
          <div className="metricCard"><dt>当前计划</dt><dd>{me.entitlement.plan.name}</dd></div>
          <div className="metricCard"><dt>权益状态</dt><dd>{entitlementLabel(me.entitlement.entitlement.status)}</dd></div>
          <div className="metricCard"><dt>AI 剩余额度</dt><dd>{me.entitlement.entitlement.ai_calls_remaining}</dd></div>
          <div className="metricCard"><dt>导出剩余额度</dt><dd>{me.entitlement.entitlement.exports_remaining}</dd></div>
          <div className="metricCard"><dt>存储上限</dt><dd>{me.entitlement.entitlement.storage_mb} MB</dd></div>
          <div className="metricCard"><dt>项目数</dt><dd>{me.accountUsage.projectCount}</dd></div>
          <div className="metricCard"><dt>页面数</dt><dd>{me.accountUsage.pageCount}</dd></div>
          <div className="metricCard"><dt>已用存储</dt><dd>{formatBytes(me.accountUsage.storageBytes)}</dd></div>
        </dl>
      </section>

      <section className="consoleSection">
        <div className="sectionSplit">
          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>套餐结构</h2>
                <p>先把套餐和额度说明清楚，支付稍后接回。</p>
              </div>
            </div>
            <div className="planDeck">
              {planResponse.plans.map((plan) => (
                <article key={plan.id} className={plan.id === me.entitlement.plan.id ? "planCard active" : "planCard"}>
                  <div className="planCardHeader">
                    <strong>{plan.name}</strong>
                    <span>{plan.price_cents ? `${(plan.price_cents / 100).toFixed(2)} ${plan.currency}` : "免费"}</span>
                  </div>
                  <small>{plan.monthly_ai_calls} 次 AI / {plan.monthly_exports} 次导出 / {plan.storage_mb} MB</small>
                </article>
              ))}
            </div>
          </div>

          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>支付状态</h2>
                <p>当前先不开放购买，避免把半成品流程暴露给用户。</p>
              </div>
            </div>
            {paidPlan ? <BillingActions planId={paidPlan.id} /> : null}
          </div>
        </div>
      </section>

      <section className="consoleSection">
        <div className="sectionSplit">
          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>最近用量</h2>
                <p>只展示最近记录，避免整页都是原始事件流。</p>
              </div>
            </div>
            <div className="activityList">
              {recentUsage.length ? recentUsage.map((event) => (
                <div key={event.id} className="activityRow">
                  <strong>{usageLabel(event.event_type)}</strong>
                  <span>x{event.quantity}</span>
                  <time>{new Date(event.created_at).toLocaleString("zh-CN", { hour12: false })}</time>
                </div>
              )) : <span className="emptyInline">暂无用量记录。</span>}
            </div>
          </div>

          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>历史订单</h2>
                <p>保留订单视图，但不再把它当成可直接购买入口。</p>
              </div>
            </div>
            <div className="activityList">
              {recentOrders.length ? recentOrders.map((order) => (
                <div key={order.id} className="activityRow stacked orderRow">
                  <div>
                    <strong>{order.plan_id.toUpperCase()}</strong>
                    <span>{(order.amount_cents / 100).toFixed(2)} {order.currency}</span>
                  </div>
                  <div>
                    <span>{order.id}</span>
                    <time>{new Date(order.created_at).toLocaleString("zh-CN", { hour12: false })}</time>
                  </div>
                  <span className={`statusPill ${order.status}`}>{orderStatusLabel(order.status)}</span>
                </div>
              )) : <span className="emptyInline">暂无订单。</span>}
            </div>
          </div>
        </div>
      </section>
    </ProductConsoleShell>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function entitlementLabel(status: string): string {
  if (status === "free") return "免费";
  if (status === "trial") return "试用";
  if (status === "active") return "已开通";
  if (status === "manual_grant") return "人工开通";
  if (status === "paused") return "已暂停";
  if (status === "canceled") return "已取消";
  if (status === "expired") return "已过期";
  if (status === "refunded") return "已退款";
  if (status === "past_due") return "待补款";
  return status;
}

function usageLabel(eventType: string): string {
  if (eventType === "project.create") return "创建项目";
  if (eventType === "page.upload") return "上传页面";
  if (eventType === "ai.boxes") return "AI 辅助画框";
  if (eventType === "export.assets") return "导出 assets.zip";
  if (eventType === "export.project") return "导出项目包";
  if (eventType === "export.project_page") return "导出单页项目包";
  return eventType;
}

function orderStatusLabel(status: string): string {
  if (status === "pending") return "待处理";
  if (status === "paid") return "已支付";
  if (status === "failed") return "失败";
  if (status === "closed") return "已关闭";
  if (status === "refunded") return "已退款";
  return status;
}
