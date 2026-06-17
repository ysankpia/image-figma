import { redirect } from "next/navigation";
import { fetchCurrentUser } from "@/app/server-auth";
import { ProductConsoleShell } from "@/components/site/ProductConsoleShell";
import { SignOutButton } from "@/components/site/SignOutButton";

export default async function SettingsPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");

  return (
    <ProductConsoleShell
      user={user}
      active="settings"
      eyebrow="Account"
      title="账号设置"
      description="先把身份、会话和项目归属边界收紧。支付和第三方登录后置，不把调试信息直接堆到页面上。"
      footerNote="当前阶段仍以本地 owner + 正常账号体系为主，密码修改、OAuth 绑定、数据导出和删除请求会在后续阶段接入。"
    >
      <section className="consoleSection">
        <div className="calloutSurface emphasis">
          <strong>设置页当前定位</strong>
          <p>这页不是占位信息板，而是账号边界说明页。谁拥有项目、谁能下载、谁能进入管理面，先在这里说清楚，避免后续继续把安全逻辑藏进接口细节里。</p>
        </div>
      </section>

      <section className="consoleSection">
        <div className="sectionHeader">
          <div>
            <h2>账号概览</h2>
            <p>这些字段已经参与项目归属、额度消费和管理端授权。</p>
          </div>
        </div>
        <dl className="metricGrid metricGridCompact">
          <div className="metricCard">
            <dt>邮箱</dt>
            <dd>{user.email}</dd>
          </div>
          <div className="metricCard">
            <dt>昵称</dt>
            <dd>{user.name}</dd>
          </div>
          <div className="metricCard">
            <dt>角色</dt>
            <dd>{user.role === "admin" ? "管理员" : "普通用户"}</dd>
          </div>
          <div className="metricCard">
            <dt>状态</dt>
            <dd>{user.status === "active" ? "正常" : "已暂停"}</dd>
          </div>
        </dl>
      </section>

      <section className="consoleSection">
        <div className="sectionSplit">
          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>会话与安全</h2>
                <p>当前先确保登录、退出、权限校验和项目归属是统一的。</p>
              </div>
            </div>
            <ul className="detailList">
              <li>工作台、账单、设置和管理页已经受登录态保护。</li>
              <li>项目、原图、切图预览和导出下载都按账号归属校验。</li>
              <li>支付回调不会通过前端返回页直接发放权益。</li>
            </ul>
            <div className="inlineActionRow">
              <SignOutButton label="退出当前会话" />
            </div>
          </div>

          <div className="toolSurface">
            <div className="sectionHeader">
              <div>
                <h2>当前边界</h2>
                <p>这里明确哪些是已经收口的，哪些还没进入正式产品合同。</p>
              </div>
            </div>
            <ul className="detailList">
              <li>已完成：会话、项目归属、额度消费、签名下载、管理入口。</li>
              <li>待收口：密码修改、第三方登录、英文界面、正式支付与发票流程。</li>
              <li>支付先暂停，后续接链动小铺或新的 agent-friendly provider。</li>
            </ul>
          </div>
        </div>
      </section>
    </ProductConsoleShell>
  );
}
